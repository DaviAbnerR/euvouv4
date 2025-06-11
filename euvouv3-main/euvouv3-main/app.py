from models import db, Usuario, Rifa, AutorizacaoCartela, Cartela, Ficha, Festa, DataFesta, Ingresso, Produto, AnalyticsEvent
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import os
import logging
import json
import urllib.request
import urllib.error
import urllib.parse
import random

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-me')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Pasta para imagens de fundo dos cards
BACKGROUND_FOLDER = os.path.join(app.root_path, 'static', 'back_img')
os.makedirs(BACKGROUND_FOLDER, exist_ok=True)
app.config['BACKGROUND_FOLDER'] = BACKGROUND_FOLDER

# Mercado Pago access token (set via environment variable)
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")

# Currency to be used with Mercado Pago items
MP_CURRENCY_ID = os.getenv("MP_CURRENCY_ID", "BRL")
app.config["MP_CURRENCY_ID"] = MP_CURRENCY_ID

# Google Analytics measurement ID (optional)
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID")
app.config["GA_MEASUREMENT_ID"] = GA_MEASUREMENT_ID

# Public URL used for external callbacks (e.g. Mercado Pago back_urls)
PUBLIC_URL = os.getenv("PUBLIC_URL")

# Reservas de fichas (numero) temporarias
RESERVA_TIMEOUT = 15 * 60  # segundos
reservas = {}

# Limite de eventos de analytics para evitar bots
BOT_EVENT_LIMIT = 50
BOT_TIME_WINDOW = 60  # segundos
recent_events = {}
blocked_ips = set()

def registrar_evento(ip):
    """Registra evento de analytics para controle de bots."""
    agora = datetime.now(timezone.utc)
    eventos = recent_events.get(ip, [])
    eventos = [t for t in eventos if (agora - t).total_seconds() < BOT_TIME_WINDOW]
    eventos.append(agora)
    recent_events[ip] = eventos
    if len(eventos) > BOT_EVENT_LIMIT:
        blocked_ips.add(ip)

def ip_bloqueado(ip):
    return ip in blocked_ips

def external_url(endpoint, **values):
    """Return absolute URL for endpoint using PUBLIC_URL if provided."""
    url = url_for(endpoint, _external=True, **values)
    if PUBLIC_URL:
        base = PUBLIC_URL.rstrip('/') + '/'
        return urllib.parse.urljoin(base, url_for(endpoint, **values).lstrip('/'))
    return url

def limpar_reservas_expiradas():
    agora = datetime.now(timezone.utc)
    expiradas = [k for k, (_, t) in reservas.items() if (agora - t).total_seconds() > RESERVA_TIMEOUT]
    for k in expiradas:
        reservas.pop(k, None)

def criar_preferencia(items):
    """Cria uma preferência de pagamento no Mercado Pago e retorna o link."""
    if not MP_ACCESS_TOKEN:
        raise RuntimeError("MP_ACCESS_TOKEN não configurado")
    for item in items:
        item.setdefault("currency_id", MP_CURRENCY_ID)
    url = "https://api.mercadopago.com/checkout/preferences"
    data = {
        "items": items,
        "back_urls": {
            "success": external_url("pagamento_status"),
            "failure": external_url("pagamento_status"),
            "pending": external_url("pagamento_status"),
        },
        "auto_return": "approved",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = json.loads(resp.read().decode())
            return resp_data.get("init_point")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        app.logger.error("Mercado Pago erro %s: %s", e.code, body)
        raise

def concluir_compra(cart):
    """Marca itens do carrinho como vendidos."""
    total = 0
    for item in cart:
        if item.get("type") == "ficha":
            ficha = Ficha.query.filter_by(id_cartela=item["cartela_id"], numero=item["numero"]).first()
            key = (item["cartela_id"], item["numero"])
            if (
                ficha
                and ficha.status == "disponivel"
                and (key not in reservas or reservas[key][0] == session["usuario_id"])
            ):
                cartela = db.session.get(Cartela, ficha.id_cartela)
                rifa = db.session.get(Rifa, cartela.id_rifa)
                ficha.status = "vendido"
                ficha.comprador_nome = session.get("usuario_nome")
                ficha.comprador_id = session["usuario_id"]
                ficha.valor_pago = rifa.valor_numero
                total += rifa.valor_numero
                reservas.pop(key, None)
        elif item.get("type") == "ingresso":
            ingresso = Ingresso(
                festa_id=item["festa_id"],
                usuario_id=session["usuario_id"],
                data_festa_id=item["data_festa_id"],
                valor_pago=item.get("valor", 0),
                nome_comprador=session.get("usuario_nome"),
                status="vendido",
            )
            db.session.add(ingresso)
            total += float(item.get("valor", 0))
        elif item.get("type") == "produto":
            produto = db.session.get(Produto, item["id"])
            if produto:
                total += produto.preco * item.get("quantidade", 1)
    db.session.commit()
    for item in cart:
        if item.get("type") == "ficha":
            reservas.pop((item["cartela_id"], item["numero"]), None)
    return total

with app.app_context():
    db.create_all()
    app.logger.info("Banco atualizado com sucesso.")
    if Produto.query.count() == 0:
        db.session.add_all([
            Produto(nome="Produto A", preco=10.0),
            Produto(nome="Produto B", preco=20.0),
            Produto(nome="Produto C", preco=30.0)
        ])
        db.session.commit()

import tasks  # noqa: E402

@app.context_processor
def inject_cart_count():
    cart = session.get('cart', [])
    if isinstance(cart, dict):
        count = sum(cart.values())
    else:
        count = len(cart)
    return {
        'cart_count': count,
        'ga_measurement_id': app.config.get('GA_MEASUREMENT_ID')
    }


@app.route('/api/carrinho/contagem')
def api_cart_count():
    cart = session.get('cart', [])
    if isinstance(cart, dict):
        count = sum(cart.values())
    else:
        count = len(cart)
    return jsonify({'count': count})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/festas")
def festas():
    return render_template("festas.html")

@app.route("/rifas")
def rifas():
    return render_template("rifas.html")


@app.route("/adicionar_ao_carrinho/<int:produto_id>")
def adicionar_ao_carrinho(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    cart = session.get('cart', [])
    # procura item existente
    found = False
    for item in cart:
        if item.get('type') == 'produto' and item.get('id') == produto_id:
            item['quantidade'] += 1
            found = True
            break
    if not found:
        cart.append({'type': 'produto', 'id': produto_id, 'quantidade': 1})
    session['cart'] = cart
    flash(f"{produto.nome} adicionado ao carrinho")
    return redirect(url_for('carrinho'))

@app.route("/carrinho")
def carrinho():
    cart = session.get('cart', [])
    itens = []
    fichas = []
    ingressos_map = {}
    total = 0
    for item in cart:
        if item.get('type') == 'produto':
            produto = db.session.get(Produto, item['id'])
            if produto:
                subtotal = produto.preco * item['quantidade']
                itens.append({'produto': produto, 'quantidade': item['quantidade'], 'total': subtotal})
                total += subtotal
        elif item.get('type') == 'ficha':
            ficha = Ficha.query.filter_by(id_cartela=item['cartela_id'], numero=item['numero']).first()
            if ficha:
                cartela = db.session.get(Cartela, ficha.id_cartela)
                rifa = db.session.get(Rifa, cartela.id_rifa)
                fichas.append({'rifa': rifa, 'numero': item['numero'], 'valor': rifa.valor_numero, 'cartela_id': item['cartela_id']})
                total += rifa.valor_numero
        elif item.get('type') == 'ingresso':
            festa = db.session.get(Festa, item['festa_id'])
            data_festa = db.session.get(DataFesta, item['data_festa_id'])
            valor = float(item.get('valor', festa.valor_ingresso if festa else 0))
            key = (item['festa_id'], item['data_festa_id'])
            if key not in ingressos_map:
                ingressos_map[key] = {
                    'festa': festa,
                    'data': data_festa,
                    'quantidade': 0,
                    'valor_unit': valor,
                    'total': 0,
                }
            ingressos_map[key]['quantidade'] += 1
            ingressos_map[key]['total'] += valor
            total += valor

    ingressos = list(ingressos_map.values())

    # limita a 15 linhas no total
    max_rows = 15
    display_itens = []
    display_fichas = []
    display_ingressos = []
    rows_used = 0
    for it in itens:
        if rows_used >= max_rows:
            break
        display_itens.append(it)
        rows_used += 1
    for f in fichas:
        if rows_used >= max_rows:
            break
        display_fichas.append(f)
        rows_used += 1
    for ing in ingressos:
        if rows_used >= max_rows:
            break
        display_ingressos.append(ing)
        rows_used += 1

    # CALCULA TAXA DE SERVIÇO
    taxa_servico = round(total * 0.075, 2)
    total_com_taxa = round(total + taxa_servico, 2)

    return render_template(
        "carrinho.html",
        itens=display_itens,
        fichas=display_fichas,
        ingressos=display_ingressos,
        total=total,
        taxa_servico=taxa_servico,
        total_com_taxa=total_com_taxa,
    )

@app.route("/api/carrinho/ficha", methods=["POST"])
def api_add_ficha():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login"}), 401
    data = request.get_json()
    id_cartela = data.get("id_cartela")
    numero = data.get("numero")
    if id_cartela is None or numero is None:
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400
    ficha = Ficha.query.filter_by(id_cartela=id_cartela, numero=numero).first()
    if not ficha or ficha.status != "disponivel":
        return jsonify({"ok": False, "msg": "Número indisponível"}), 400

    limpar_reservas_expiradas()
    key = (id_cartela, numero)
    if key in reservas and reservas[key][0] != session["usuario_id"]:
        return jsonify({"ok": False, "msg": "Número reservado"}), 400

    cart = session.get("cart", [])
    for item in cart:
        if item.get("type") == "ficha" and item.get("cartela_id") == id_cartela and item.get("numero") == numero:
            reservas[key] = (session["usuario_id"], datetime.now(timezone.utc))
            return jsonify({"ok": True})

    total_fichas = sum(1 for i in cart if i.get("type") == "ficha")
    if total_fichas >= 10:
        return jsonify({"ok": False, "msg": "Limite de 10 números por vez"}), 400

    cart.append({"type": "ficha", "cartela_id": id_cartela, "numero": numero})
    session["cart"] = cart
    reservas[key] = (session["usuario_id"], datetime.now(timezone.utc))
    return jsonify({"ok": True})

@app.route("/api/carrinho/ficha/remover", methods=["POST"])
def api_remove_ficha():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login"}), 401
    data = request.get_json()
    cartela_id = data.get("cartela_id")
    numero = data.get("numero")
    if cartela_id is None or numero is None:
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400
    cart = session.get("cart", [])
    nova = []
    removido = False
    for item in cart:
        if not removido and item.get("type") == "ficha" and item.get("cartela_id") == cartela_id and item.get("numero") == numero:
            removido = True
            continue
        nova.append(item)
    session["cart"] = nova
    key = (cartela_id, numero)
    if key in reservas and reservas[key][0] == session["usuario_id"]:
        reservas.pop(key, None)
    return jsonify({"ok": True})

@app.route("/api/carrinho/ingresso", methods=["POST"])
def api_add_ingresso():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login"}), 401
    data = request.get_json()
    festa_id = data.get("festa_id")
    data_festa_id = data.get("data_festa_id")
    try:
        festa_id = int(festa_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400
    try:
        data_festa_id = int(data_festa_id) if data_festa_id is not None else None
    except (TypeError, ValueError):
        data_festa_id = None
    valor = float(data.get("valor", 0))
    quantidade = int(data.get("quantidade", 1) or 1)
    cart = session.get("cart", [])
    for _ in range(max(1, quantidade)):
        cart.append({"type": "ingresso", "festa_id": festa_id, "data_festa_id": data_festa_id, "valor": valor})
    session["cart"] = cart
    return jsonify({"ok": True})

@app.route("/api/carrinho/ingresso/remover", methods=["POST"])
def api_remove_ingresso():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login"}), 401
    data = request.get_json()
    festa_id = data.get("festa_id")
    data_festa_id = data.get("data_festa_id")
    try:
        festa_id = int(festa_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400
    try:
        data_festa_id = int(data_festa_id) if data_festa_id is not None else None
    except (TypeError, ValueError):
        data_festa_id = None
    cart = session.get("cart", [])
    nova = []
    removido = False
    for item in cart:
        if (
            not removido
            and item.get("type") == "ingresso"
            and item.get("festa_id") == festa_id
            and item.get("data_festa_id") == data_festa_id
        ):
            removido = True
            continue
        nova.append(item)
    session["cart"] = nova
    return jsonify({"ok": True})

@app.route("/api/carrinho/ingresso/remover_todos", methods=["POST"])
def api_remove_todos_ingressos():
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login"}), 401
    data = request.get_json()
    festa_id = data.get("festa_id")
    data_festa_id = data.get("data_festa_id")
    try:
        festa_id = int(festa_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "msg": "Dados inválidos"}), 400
    try:
        data_festa_id = int(data_festa_id) if data_festa_id is not None else None
    except (TypeError, ValueError):
        data_festa_id = None
    cart = session.get("cart", [])
    nova = [
        item for item in cart
        if not (
            item.get("type") == "ingresso"
            and item.get("festa_id") == festa_id
            and item.get("data_festa_id") == data_festa_id
        )
    ]
    session["cart"] = nova
    return jsonify({"ok": True})

@app.route("/finalizar_compra", methods=["POST"])
def finalizar_compra():
    if "usuario_id" not in session:
        flash("Faça login para finalizar a compra.")
        return redirect(url_for("login"))
    cart = session.get("cart", [])
    items = []
    total = 0
    for item in cart:
        if item.get("type") == "produto":
            produto = db.session.get(Produto, item["id"])
            if produto:
                items.append({
                    "title": produto.nome,
                    "quantity": item.get("quantidade", 1),
                    "unit_price": float(produto.preco),
                })
                total += float(produto.preco) * item.get("quantidade", 1)
        elif item.get("type") == "ficha":
            ficha = Ficha.query.filter_by(id_cartela=item["cartela_id"], numero=item["numero"]).first()
            if ficha and ficha.status == "disponivel":
                cartela = db.session.get(Cartela, ficha.id_cartela)
                rifa = db.session.get(Rifa, cartela.id_rifa)
                items.append({
                    "title": f"Número {item['numero']} - {rifa.titulo}",
                    "quantity": 1,
                    "unit_price": float(rifa.valor_numero),
                })
                total += float(rifa.valor_numero)
        elif item.get("type") == "ingresso":
            festa = db.session.get(Festa, item["festa_id"])
            data_festa = db.session.get(DataFesta, item["data_festa_id"])
            titulo = f"Ingresso - {festa.nome}" if festa else "Ingresso"
            if data_festa:
                titulo += f" ({data_festa.data.strftime('%d/%m/%Y')})"
            valor_item = float(item.get("valor", festa.valor_ingresso if festa else 0))
            items.append({
                "title": titulo,
                "quantity": 1,
                "unit_price": valor_item,
            })
            total += valor_item

    # NOVO: Adicione a taxa de serviço como item extra!
    taxa_servico = round(total * 0.075, 2)
    if taxa_servico > 0:
        items.append({
            "title": "Taxa de Serviço",
            "quantity": 1,
            "unit_price": taxa_servico,
        })

    if not items:
        flash("Seu carrinho está vazio.")
        return redirect(url_for("carrinho"))

    try:
        pref_url = criar_preferencia(items)
        session["cart_data"] = cart
        return redirect(pref_url)
    except Exception:
        app.logger.exception("Erro ao criar preferência")
        flash("Erro ao iniciar pagamento.")
        return redirect(url_for("carrinho"))


@app.route("/pagamento_status")
def pagamento_status():
    status = request.args.get("status") or request.args.get("collection_status")
    if status == "approved":
        cart = session.get("cart_data", [])
        concluir_compra(cart)
        session["cart"] = []
        session.pop("cart_data", None)
        flash("Pagamento aprovado! Compra finalizada.")
    else:
        flash("Pagamento não concluído.")
    return redirect(url_for("carrinho"))

@app.route("/painel")
def painel():
    if "usuario_id" not in session:
        flash("Você precisa estar logado para acessar o painel.")
        return redirect(url_for("login"))

    rifas = []
    festas = []
    minhas_fichas = []
    meus_ingressos = []
    usuario = db.session.get(Usuario, session["usuario_id"])
    if session["usuario_tipo"] in ["organizador", "administrador"]:
        rifas = Rifa.query.filter_by(id_organizador=session["usuario_id"]).all()
        for rifa in rifas:
            rifa.cartelas = Cartela.query.filter_by(id_rifa=rifa.id).all()
            rifa.fichas_vendidas = sum(
                Ficha.query.filter_by(id_cartela=cartela.id, status='vendido').count()
                for cartela in rifa.cartelas
            )
        festas = Festa.query.filter_by(id_organizador=session["usuario_id"]).all()

    minhas_fichas = (
        db.session.query(Ficha, Cartela, Rifa)
        .join(Cartela, Ficha.id_cartela == Cartela.id)
        .join(Rifa, Cartela.id_rifa == Rifa.id)
        .filter(Ficha.comprador_id == session["usuario_id"])
        .all()
    )
    meus_ingressos = (
        db.session.query(Ingresso, Festa, DataFesta)
        .join(Festa, Ingresso.festa_id == Festa.id)
        .outerjoin(DataFesta, Ingresso.data_festa_id == DataFesta.id)
        .filter(Ingresso.usuario_id == session["usuario_id"])
        .all()
    )

    return render_template(
        "painel.html",
        rifas=rifas,
        festas=festas,
        minhas_fichas=minhas_fichas,
        meus_ingressos=meus_ingressos,
        usuario=usuario
    )

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"]
        email = request.form["email"]
        senha = request.form["senha"]

        if Usuario.query.filter_by(email=email).first():
            flash("E-mail já cadastrado.")
            return redirect(url_for("cadastro"))

        usuario = Usuario(nome=nome, email=email, tipo="comum")
        usuario.set_senha(senha)
        db.session.add(usuario)
        db.session.commit()
        flash("Cadastro realizado! Faça login.")
        return redirect(url_for("login"))

    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        senha = request.form["senha"]
        app.logger.info("Tentativa de login com: %s", email)

        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.verificar_senha(senha):
            session["usuario_id"] = usuario.id
            session["usuario_nome"] = usuario.nome
            session["usuario_tipo"] = usuario.tipo
            flash("Login realizado com sucesso!")
            return redirect(url_for("painel"))
        
        flash("Credenciais inválidas.")

    return render_template("login.html")

@app.route("/logout")
def logout():
    cart = session.get("cart", [])
    for item in cart:
        if item.get("type") == "ficha":
            reservas.pop((item["cartela_id"], item["numero"]), None)
    session.clear()
    flash("Você saiu da conta.")
    return redirect(url_for("index"))


@app.route("/atualizar_dados", methods=["POST"])
def atualizar_dados():
    if "usuario_id" not in session:
        flash("Você precisa estar logado.")
        return redirect(url_for("login"))

    usuario = db.session.get(Usuario, session["usuario_id"])
    usuario.nome = request.form.get("nome")
    usuario.email = request.form.get("email")
    usuario.telefone = request.form.get("telefone")
    db.session.commit()
    session["usuario_nome"] = usuario.nome
    flash("Dados atualizados com sucesso!")
    return redirect(url_for("painel"))

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if "usuario_id" not in session or session.get("usuario_tipo") != "administrador":
        flash("Acesso negado. Somente administradores podem acessar.")
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = request.form["user_id"]
        novo_tipo = request.form["novo_tipo"]

        usuario = db.session.get(Usuario, user_id)
        if usuario:
            usuario.tipo = novo_tipo
            db.session.commit()
            flash(f"Tipo de {usuario.nome} atualizado para {novo_tipo}.")

    usuarios = Usuario.query.all()
    return render_template("admin.html", usuarios=usuarios)

@app.route("/criar_rifa", methods=["GET", "POST"])
def criar_rifa():
    if "usuario_id" not in session or session.get("usuario_tipo") != "organizador":
        flash("Apenas organizadores podem criar rifas.")
        return redirect(url_for("login"))

    usuarios = Usuario.query.all()

    if request.method == "POST":
        titulo = request.form["titulo"]
        valor_numero = float(request.form["valor_numero"])
        limite = request.form.get("limite_numeros")
        limite = int(limite) if limite else None

        nova_rifa = Rifa(
            titulo=titulo,
            valor_numero=valor_numero,
            limite_numeros=limite,
            id_organizador=session["usuario_id"]
        )
        db.session.add(nova_rifa)
        db.session.commit()

        ids_autorizados = request.form.getlist("usuarios_autorizados")
        for id_user in ids_autorizados:
            autorizacao = AutorizacaoCartela(
                id_rifa=nova_rifa.id,
                id_usuario=int(id_user)
            )
            db.session.add(autorizacao)

        db.session.commit()
        flash("Rifa criada com sucesso!")
        return redirect(url_for("painel"))

    return render_template("criar_rifa.html", usuarios=usuarios)

@app.route("/minhas_cartelas", methods=["GET", "POST"])
def minhas_cartelas():
    if "usuario_id" not in session:
        flash("Você precisa estar logado.")
        return redirect(url_for("login"))

    subquery = db.session.query(AutorizacaoCartela.id_rifa).filter_by(id_usuario=session["usuario_id"])
    rifas_autorizadas = Rifa.query.filter(Rifa.id.in_(subquery), Rifa.status == "em_andamento").all()

    if request.method == "POST":
        id_rifa = int(request.form["id_rifa"])
        rifa = db.session.get(Rifa, id_rifa)

        autorizado = AutorizacaoCartela.query.filter_by(id_rifa=id_rifa, id_usuario=session["usuario_id"]).first()
        if not autorizado:
            flash("Você não tem permissão para criar cartela nesta rifa.")
            return redirect(url_for("minhas_cartelas"))

        proximo_num = Cartela.query.filter_by(id_rifa=id_rifa).count() + 1

        nova_cartela = Cartela(
            id_rifa=id_rifa,
            numero_cartela=proximo_num,
            id_usuario_criador=session["usuario_id"]
        )
        db.session.add(nova_cartela)
        db.session.commit()

        # Cria 50 fichas numeradas
        for i in range(50):
            ficha = Ficha(id_cartela=nova_cartela.id, numero=i)
            db.session.add(ficha)
        db.session.commit()

        flash(f"Cartela #{proximo_num} criada para a rifa '{rifa.titulo}'.")
        return redirect(url_for("minhas_cartelas"))

    cartelas = Cartela.query.filter_by(id_usuario_criador=session["usuario_id"]).all()
    return render_template("minhas_cartelas.html", rifas=rifas_autorizadas, cartelas=cartelas)

@app.route("/cartela/<int:id_cartela>", methods=["GET", "POST"])
def cartela(id_cartela):
    if "usuario_id" not in session:
        flash("Faça login para acessar.")
        return redirect(url_for("login"))

    cartela = Cartela.query.get_or_404(id_cartela)
    rifa = db.session.get(Rifa, cartela.id_rifa)

    if session["usuario_id"] != cartela.id_usuario_criador and session["usuario_id"] != rifa.id_organizador:
        flash("Você não tem permissão para acessar esta cartela.")
        return redirect(url_for("painel"))

    fichas = Ficha.query.filter_by(id_cartela=id_cartela).all()

    if request.method == "POST":
        numero = int(request.form["numero"])
        nome = request.form["comprador_nome"]
        ficha = Ficha.query.filter_by(id_cartela=id_cartela, numero=numero).first()
        # Já tem cartela e rifa acima

        if ficha and ficha.status == "disponivel":
            ficha.status = "vendido"
            ficha.comprador_nome = nome
            ficha.comprador_id = session.get("usuario_id")
            ficha.valor_pago = rifa.valor_numero
            db.session.commit()
            flash(f"Número {numero} vendido para {nome} por R$ {ficha.valor_pago:.2f}.")
        else:
            flash("Número já foi vendido ou inválido.")
        return redirect(url_for("cartela", id_cartela=id_cartela))

    return render_template("cartela.html", cartela=cartela, rifa=rifa, fichas=fichas)

@app.route("/api/rifa/<int:id_rifa>/cartelas")
def api_cartelas(id_rifa):
    cartelas = Cartela.query.filter_by(id_rifa=id_rifa).all()
    dados = []
    for c in cartelas:
        usuario = db.session.get(Usuario, c.id_usuario_criador)
        fichas_vendidas = Ficha.query.filter_by(id_cartela=c.id, status='vendido').count()
        dados.append({
            "id": c.id,
            "numero_cartela": c.numero_cartela,
            "criador": usuario.nome,
            "vendidos": fichas_vendidas,
            "id_rifa": c.id_rifa
        })
    return jsonify(dados)

@app.route("/api/cartela/<int:id_cartela>")
def api_fichas_cartela(id_cartela):
    limpar_reservas_expiradas()
    fichas = Ficha.query.filter_by(id_cartela=id_cartela).all()
    dados = []
    for f in fichas:
        status = f.status
        if status == "disponivel" and (f.id_cartela, f.numero) in reservas:
            status = "reservado"
        dados.append({"numero": f.numero, "status": status, "comprador": f.comprador_nome or ""})
    return jsonify(dados)

@app.route("/api/rifa/<int:id>/alterar_preco", methods=["POST"])
def alterar_preco(id):
    if "usuario_id" not in session:
        return jsonify({"message": "Não autorizado"}), 403

    rifa = Rifa.query.get_or_404(id)
    if rifa.id_organizador != session["usuario_id"]:
        return jsonify({"message": "Apenas o organizador pode alterar"}), 403

    novo_valor = float(request.form["valor"])
    if novo_valor < 1:
        return jsonify({"message": "O preço mínimo é R$ 1,00"}), 400
    rifa.valor_numero = novo_valor
    db.session.commit()
    return jsonify({"message": "Preço atualizado com sucesso!"})

@app.route("/api/rifa/<int:id_rifa>")
def api_info_rifa(id_rifa):
    rifa = Rifa.query.get_or_404(id_rifa)
    vendedores = (
        db.session.query(Usuario)
        .join(AutorizacaoCartela, AutorizacaoCartela.id_usuario == Usuario.id)
        .filter(AutorizacaoCartela.id_rifa == id_rifa)
        .all()
    )
    cartelas = Cartela.query.filter_by(id_rifa=id_rifa).all()
    fichas = Ficha.query.join(Cartela).filter(Cartela.id_rifa == id_rifa).all()
    fichas_vendidas = [f for f in fichas if f.status == "vendido"]
    total_fichas = len(fichas)
    total_vendido = sum(f.valor_pago or 0 for f in fichas_vendidas)

    vencedor_nome = None
    numero_vencedor = None
    if rifa.id_ficha_vencedora:
        ficha_venc = db.session.get(Ficha, rifa.id_ficha_vencedora)
        cartela_venc = db.session.get(Cartela, ficha_venc.id_cartela) if ficha_venc else None
        if ficha_venc:
            vencedor_nome = ficha_venc.comprador_nome
            numero_vencedor = (cartela_venc.numero_cartela - 1) * 50 + ficha_venc.numero if cartela_venc else ficha_venc.numero

    # ------- CORREÇÃO DO TIMEZONE -------
    pode_sortear = False
    if (
        'usuario_id' in session
        and session['usuario_id'] == rifa.id_organizador
        and rifa.data_fim
        and rifa.status == 'em_andamento'
    ):
        from datetime import timezone, datetime
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        data_fim_naive = rifa.data_fim.replace(tzinfo=None) if hasattr(rifa.data_fim, "replace") else rifa.data_fim
        if data_fim_naive and now_naive >= data_fim_naive:
            pode_sortear = True
    # -------------------------------------

    def formatar_data(dt):
        if not dt: return ''
        if isinstance(dt, str): dt = dt[:10]
        if isinstance(dt, str):
            try:
                # '2025-05-31'
                return datetime.strptime(dt, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                return dt
        return dt.strftime("%d/%m/%Y")    

    return jsonify({
        "titulo": rifa.titulo,
        "descricao_premio": getattr(rifa, 'descricao_premio', ''),
        "valor_atual": rifa.valor_numero,
        "data_inicio": str(getattr(rifa, 'data_inicio', '')),
        "data_fim": str(getattr(rifa, 'data_fim', '')),
        "quantidade_cartelas": len(cartelas),
        "total_fichas": total_fichas,
        "fichas_vendidas": len(fichas_vendidas),
        "valor_total_vendido": total_vendido,
        "vendedores": [{"id": v.id, "nome": v.nome} for v in vendedores],
        "imagem_fundo": rifa.imagem_fundo,
        "status": rifa.status,
        "pode_sortear": pode_sortear,
        "vencedor_nome": vencedor_nome,
        "numero_vencedor": numero_vencedor
    })


@app.route("/api/usuarios")
def api_usuarios():
    if "usuario_id" not in session or session.get("usuario_tipo") != "administrador":
        return jsonify([])
    usuarios = Usuario.query.all()
    usuarios_data = []
    for user in usuarios:
        usuarios_data.append({
            "id": user.id,
            "nome": user.nome,
            "email": user.email,
            "tipo": user.tipo
        })
    return jsonify(usuarios_data)

@app.route("/api/usuario/<int:user_id>/alterar_tipo", methods=["POST"])
def api_alterar_tipo(user_id):
    if "usuario_id" not in session or session.get("usuario_tipo") != "administrador":
        return jsonify({"ok": False})
    novo_tipo = request.form.get("novo_tipo")
    usuario = db.session.get(Usuario, user_id)
    if usuario:
        usuario.tipo = novo_tipo
        db.session.commit()
        return jsonify({"ok": True})
    return jsonify({"ok": False})

@app.route("/api/rifa/<int:id_rifa>/criar_cartela", methods=["POST"])
def api_criar_cartela(id_rifa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Precisa estar logado"}), 401

    # Só pode criar se estiver autorizado na rifa
    autorizado = AutorizacaoCartela.query.filter_by(id_rifa=id_rifa, id_usuario=session["usuario_id"]).first()
    if not autorizado:
        return jsonify({"ok": False, "msg": "Você não está autorizado para esta rifa."}), 403

    proximo_num = Cartela.query.filter_by(id_rifa=id_rifa).count() + 1
    nova_cartela = Cartela(
        id_rifa=id_rifa,
        numero_cartela=proximo_num,
        id_usuario_criador=session["usuario_id"]
    )
    db.session.add(nova_cartela)
    db.session.commit()
    # Cria 50 fichas
    for i in range(50):
        ficha = Ficha(id_cartela=nova_cartela.id, numero=i)
        db.session.add(ficha)
    db.session.commit()
    return jsonify({"ok": True, "msg": f"Cartela criada! #{proximo_num}"})

@app.route("/api/rifa/<int:id_rifa>/criar_cartela_para", methods=["POST"])
def api_criar_cartela_para(id_rifa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Precisa estar logado"}), 401

    # Só organizador pode criar para outro usuário
    rifa = db.session.get(Rifa, id_rifa)
    if not rifa or rifa.id_organizador != session["usuario_id"]:
        return jsonify({"ok": False, "msg": "Somente o organizador pode criar cartela para outros usuários"}), 403

    id_usuario = request.form.get("id_usuario")
    if not id_usuario:
        return jsonify({"ok": False, "msg": "ID do usuário obrigatório"}), 400

    id_usuario = int(id_usuario)
    autorizado = AutorizacaoCartela.query.filter_by(id_rifa=id_rifa, id_usuario=id_usuario).first()
    if not autorizado:
        return jsonify({"ok": False, "msg": "Usuário não autorizado para esta rifa"}), 403

    proximo_num = Cartela.query.filter_by(id_rifa=id_rifa).count() + 1
    nova_cartela = Cartela(
        id_rifa=id_rifa,
        numero_cartela=proximo_num,
        id_usuario_criador=id_usuario
    )
    db.session.add(nova_cartela)
    db.session.commit()
    # Cria 50 fichas
    for i in range(50):
        ficha = Ficha(id_cartela=nova_cartela.id, numero=i)
        db.session.add(ficha)
    db.session.commit()
    return jsonify({"ok": True, "msg": f"Cartela criada para o usuário {id_usuario}! #{proximo_num}"})

@app.route("/api/rifa/<int:id_rifa>/autorizados")
def api_rifa_autorizados(id_rifa):
    # Lista todos os usuários autorizados para criar cartela nessa rifa
    autorizacoes = AutorizacaoCartela.query.filter_by(id_rifa=id_rifa).all()
    usuarios = []
    for aut in autorizacoes:
        usuario = db.session.get(Usuario, aut.id_usuario)
        if usuario:
            usuarios.append({
                "id": usuario.id,
                "nome": usuario.nome
            })
    return jsonify(usuarios)

@app.route("/api/rifa/criar", methods=["POST"])
def api_criar_rifa():
    if "usuario_id" not in session or session["usuario_tipo"] not in ["organizador", "administrador"]:
        return jsonify({"ok": False, "msg": "Não autorizado."}), 403

    try:
        data = request.get_json()
        app.logger.debug("DEBUG - Data recebido: %s", data)
        valor_raw = data.get("valor_numero")
        if valor_raw is None or valor_raw == '' or str(valor_raw).lower() == 'nan':
            raise ValueError("Informe um valor válido para o preço!")
        valor_numero = float(valor_raw)
        if valor_numero < 1:
            raise ValueError("O preço mínimo por número é R$ 1,00")

        # NOVO: Converter datas de string para objeto date
        data_inicio = data.get("data_inicio")
        data_fim = data.get("data_fim")
        data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
        data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else None

        nova_rifa = Rifa(
            titulo=data.get("titulo"),
            descricao_premio=data.get("descricao_premio"),
            valor_numero=valor_numero,
            data_inicio=data_inicio,
            data_fim=data_fim,
            limite_numeros=int(data.get("limite_numeros")) if data.get("limite_numeros") else None,
            id_organizador=session["usuario_id"]
        )
        db.session.add(nova_rifa)
        db.session.commit()
        return jsonify({"ok": True, "msg": "Rifa criada com sucesso!"})
    except Exception as e:
        app.logger.error("ERRO AO CRIAR RIFA: %s", str(e))
        return jsonify({"ok": False, "msg": f"Erro ao criar rifa: {str(e)}"}), 400
    
@app.route("/api/rifa/<int:id_rifa>/possiveis_vendedores")
def api_possiveis_vendedores(id_rifa):
    # Todos usuários do tipo 'comum' que NÃO estão na lista de autorizados desta rifa
    subquery = db.session.query(AutorizacaoCartela.id_usuario).filter_by(id_rifa=id_rifa)
    usuarios = Usuario.query.filter(
        ~Usuario.id.in_(subquery)
    ).all()
    return jsonify([
        {
            "id": u.id,
            # Apenas as DUAS primeiras palavras
            "nome": " ".join(u.nome.split()[:2]),
            "email": u.email
        } for u in usuarios
    ])

@app.route("/api/rifa/<int:id_rifa>/adicionar_vendedor", methods=["POST"])
def api_adicionar_vendedor(id_rifa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Não autorizado"}), 401
    rifa = db.session.get(Rifa, id_rifa)
    if not rifa or rifa.id_organizador != session["usuario_id"]:
        return jsonify({"ok": False, "msg": "Apenas o organizador pode adicionar vendedores"}), 403

    id_usuario = request.form.get("id_usuario")
    if not id_usuario:
        return jsonify({"ok": False, "msg": "ID do usuário obrigatório"}), 400
    id_usuario = int(id_usuario)
    # Verifica se já é autorizado
    if AutorizacaoCartela.query.filter_by(id_rifa=id_rifa, id_usuario=id_usuario).first():
        return jsonify({"ok": False, "msg": "Usuário já autorizado."}), 400

    autorizacao = AutorizacaoCartela(id_rifa=id_rifa, id_usuario=id_usuario)
    db.session.add(autorizacao)
    db.session.commit()
    return jsonify({"ok": True, "msg": "Vendedor adicionado com sucesso!"})

@app.route("/api/rifa/<int:id_rifa>/remover_vendedor", methods=["POST"])
def api_remover_vendedor(id_rifa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Não autorizado"}), 401
    rifa = db.session.get(Rifa, id_rifa)
    if not rifa or rifa.id_organizador != session["usuario_id"]:
        return jsonify({"ok": False, "msg": "Apenas o organizador pode remover vendedores"}), 403

    id_usuario = request.form.get("id_usuario")
    if not id_usuario:
        return jsonify({"ok": False, "msg": "ID do usuário obrigatório"}), 400
    id_usuario = int(id_usuario)
    autorizacao = AutorizacaoCartela.query.filter_by(id_rifa=id_rifa, id_usuario=id_usuario).first()
    if not autorizacao:
        return jsonify({"ok": False, "msg": "Usuário não autorizado"}), 400

    db.session.delete(autorizacao)
    db.session.commit()
    return jsonify({"ok": True, "msg": "Vendedor removido com sucesso!"})

@app.route('/api/rifa/<int:id_rifa>/imagem_fundo', methods=['POST'])
def api_upload_rifa_bg(id_rifa):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'msg': 'Não autorizado'}), 401
    rifa = db.session.get(Rifa, id_rifa)
    if not rifa or (session['usuario_id'] != rifa.id_organizador and session.get('usuario_tipo') != 'administrador'):
        return jsonify({'ok': False, 'msg': 'Permissão negada'}), 403
    file = request.files.get('imagem')
    url = request.form.get('url')
    if not file and not url:
        return jsonify({'ok': False, 'msg': 'Arquivo ou URL não enviado'}), 400
    if file:
        original_name = secure_filename(file.filename)
        filename = f"rifa_{id_rifa}_{int(datetime.now(timezone.utc).timestamp())}_{original_name}"
        path = os.path.join(app.config['BACKGROUND_FOLDER'], filename)
        file.save(path)
        rifa.imagem_fundo = '/static/back_img/' + filename
    else:
        rifa.imagem_fundo = url
    db.session.commit()
    return jsonify({'ok': True, 'url': rifa.imagem_fundo})


def sortear_rifa(rifa):
    """Seleciona e registra o vencedor de uma rifa."""
    fichas = (
        Ficha.query.join(Cartela)
        .filter(Cartela.id_rifa == rifa.id, Ficha.status == 'vendido')
        .all()
    )
    if not fichas:
        return None
    ficha_vencedora = random.choice(fichas)
    rifa.id_ficha_vencedora = ficha_vencedora.id
    rifa.status = 'finalizada'
    db.session.commit()
    return ficha_vencedora

@app.route('/api/rifa/<int:id_rifa>/sortear', methods=['POST'])
def api_sortear_rifa(id_rifa):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'msg': 'Não autorizado'}), 401
    rifa = db.session.get(Rifa, id_rifa)
    if not rifa or (session['usuario_id'] != rifa.id_organizador and session.get('usuario_tipo') != 'administrador'):
        return jsonify({'ok': False, 'msg': 'Permissão negada'}), 403
    if rifa.status != 'em_andamento':
        return jsonify({'ok': False, 'msg': 'Rifa já finalizada'}), 400
    if not rifa.data_fim or datetime.now(timezone.utc) < rifa.data_fim:
        return jsonify({'ok': False, 'msg': 'Data do sorteio ainda não atingida'}), 400
    ficha_vencedora = sortear_rifa(rifa)
    if not ficha_vencedora:
        return jsonify({'ok': False, 'msg': 'Nenhuma ficha vendida'}), 400
    return jsonify({'ok': True, 'ganhador_nome': ficha_vencedora.comprador_nome, 'numero': ficha_vencedora.numero, 'cartela': ficha_vencedora.id_cartela})

@app.route("/api/festa/criar", methods=["POST"])
def api_criar_festa():
    if "usuario_id" not in session or session.get("usuario_tipo") not in ["organizador", "administrador"]:
        return jsonify({"ok": False, "msg": "Não autorizado."}), 403

    data = request.get_json()
    try:
        festa = Festa(
            nome=data.get("nome"),
            local=data.get("local"),
            descricao=data.get("descricao"),
            valor_ingresso=float(data.get("valor_ingresso", 0)),
            id_organizador=session["usuario_id"]
        )
        db.session.add(festa)
        db.session.commit()

        # Corrija aqui: converta string para date antes de criar DataFesta!
        from datetime import datetime
        for data_str in data.get("datas", []):
            data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
            data_festa = DataFesta(id_festa=festa.id, data=data_obj)
            db.session.add(data_festa)
        db.session.commit()

        return jsonify({"ok": True, "msg": "Festa criada com sucesso!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "msg": f"Erro ao criar festa: {str(e)}"}), 400

    
@app.route("/api/festa/<int:id_festa>/vender_ingresso", methods=["POST"])
def api_vender_ingresso(id_festa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Faça login para comprar ingresso."}), 401

    data = request.get_json()
    usuario_id = session["usuario_id"]
    valor_pago = float(data.get("valor_pago"))  # O valor que está sendo pago agora (pega do valor atual exibido)
    data_festa_id = data.get("data_festa_id")   # Qual das datas da festa

    ingresso = Ingresso(
        festa_id=id_festa,
        usuario_id=usuario_id,
        valor_pago=valor_pago,
        data_festa_id=data_festa_id,
        nome_comprador=session.get("usuario_nome"),
        status="vendido"
    )
    db.session.add(ingresso)
    db.session.commit()
    return jsonify({"ok": True, "msg": "Ingresso comprado com sucesso!"})

@app.route("/api/festa/<int:id_festa>")
def api_info_festa(id_festa):
    festa = Festa.query.get_or_404(id_festa)
    ingressos = Ingresso.query.filter_by(festa_id=id_festa, status="vendido").all()
    valor_total = sum(i.valor_pago or 0 for i in ingressos)
    total_vendidos = len(ingressos)
    datas = [{"id": d.id, "data": d.data.strftime("%Y-%m-%d")} for d in festa.datas]
    return jsonify({
        "id": festa.id,
        "nome": festa.nome,
        "local": festa.local,
        "descricao": festa.descricao,
        "valor_ingresso": festa.valor_ingresso,
        "datas": datas,
        "organizador_id": festa.id_organizador,
        "total_vendidos": total_vendidos,
        "valor_total": valor_total,
        "imagem_fundo": festa.imagem_fundo
    })

@app.route("/api/festa/<int:id_festa>/alterar_preco", methods=["POST"])
def api_alterar_preco_festa(id_festa):
    if "usuario_id" not in session:
        return jsonify({"ok": False, "msg": "Não autorizado."}), 403

    festa = Festa.query.get_or_404(id_festa)
    # Organizador ou administrador pode alterar
    if session["usuario_id"] != festa.id_organizador and session.get("usuario_tipo") != "administrador":
        return jsonify({"ok": False, "msg": "Apenas o organizador pode alterar!"}), 403

    # Aqui aceita o valor do form!
    novo_valor = request.form.get("novo_valor")
    if not novo_valor:
        return jsonify({"ok": False, "msg": "Valor não enviado!"}), 400

    try:
        novo_valor = float(novo_valor)
        if novo_valor < 1:
            return jsonify({"ok": False, "msg": "O valor mínimo é R$ 1,00"}), 400
        festa.valor_ingresso = novo_valor
        db.session.commit()
        return jsonify({"ok": True, "message": "Preço atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Valor inválido ou erro: {str(e)}"}), 400

@app.route('/api/festa/<int:id_festa>/imagem_fundo', methods=['POST'])
def api_upload_festa_bg(id_festa):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'msg': 'Não autorizado'}), 401
    festa = Festa.query.get_or_404(id_festa)
    if session['usuario_id'] != festa.id_organizador and session.get('usuario_tipo') != 'administrador':
        return jsonify({'ok': False, 'msg': 'Permissão negada'}), 403
    file = request.files.get('imagem')
    url = request.form.get('url')
    if not file and not url:
        return jsonify({'ok': False, 'msg': 'Arquivo ou URL não enviado'}), 400
    if file:
        original_name = secure_filename(file.filename)
        filename = f"festa_{id_festa}_{int(datetime.now(timezone.utc).timestamp())}_{original_name}"
        path = os.path.join(app.config['BACKGROUND_FOLDER'], filename)
        file.save(path)
        festa.imagem_fundo = '/static/back_img/' + filename
    else:
        festa.imagem_fundo = url
    db.session.commit()
    return jsonify({'ok': True, 'url': festa.imagem_fundo})
    
@app.route("/api/festas")
def api_listar_festas():
    festas = Festa.query.all()
    return jsonify([
        {
            "id": f.id,
            "nome": f.nome,
            "local": f.local,
            "descricao": f.descricao,
            "valor_ingresso": f.valor_ingresso,
            "datas": [d.data.strftime("%Y-%m-%d") for d in f.datas],
            "imagem_fundo": f.imagem_fundo
        } for f in festas
    ])

@app.route("/festa/<int:id>")
def pagina_festa(id):
    return render_template("festa_detalhe.html", id_festa=id)

@app.route("/rifa/<int:id>")
def pagina_rifa(id):
    return render_template("rifa_detalhe.html", id_rifa=id)

@app.route("/api/rifas")
def api_listar_rifas():
    rifas = Rifa.query.filter_by(status="em_andamento").all()
    return jsonify([
        {
            "id": r.id,
            "titulo": r.titulo,
            "descricao_premio": r.descricao_premio,
            "valor_numero": r.valor_numero,
            "data_fim": r.data_fim.strftime("%Y-%m-%d") if r.data_fim else "",
            "imagem_premio": r.imagem_premio,
            "imagem_fundo": r.imagem_fundo
        } for r in rifas
    ])


@app.route("/api/analytics", methods=["POST"])
def api_analytics():
    data = request.get_json() or {}
    ip = request.remote_addr
    registrar_evento(ip)
    if ip_bloqueado(ip):
        return jsonify({"ok": False, "msg": "Too many requests"}), 429

    event = AnalyticsEvent(
        visitor_id=data.get("visitor_id"),
        path=data.get("path"),
        referrer=data.get("referrer"),
        event_type=data.get("type"),
        time_on_page=data.get("time_on_page"),
        ad_id=data.get("ad_id"),
        ip=ip,
        user_agent=request.headers.get("User-Agent"),
    )
    db.session.add(event)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/relatorio/anuncio/<ad_id>")
def api_relatorio_anuncio(ad_id):
    """Retorna métricas básicas de um anúncio."""
    impressoes = AnalyticsEvent.query.filter_by(event_type="ad_impression", ad_id=ad_id).count()
    cliques = AnalyticsEvent.query.filter_by(event_type="ad_click", ad_id=ad_id).count()
    visualizacoes = (
        db.session.query(AnalyticsEvent.visitor_id)
        .filter_by(event_type="ad_impression", ad_id=ad_id)
        .distinct()
        .count()
    )
    ctr = (cliques / impressoes * 100) if impressoes else 0.0
    return jsonify({
        "ad_id": ad_id,
        "visualizacoes": visualizacoes,
        "impressoes": impressoes,
        "cliques": cliques,
        "ctr": ctr,
    })



if __name__ == "__main__":
    debug_env = os.getenv("DEBUG", "False").lower()
    debug_mode = debug_env in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
