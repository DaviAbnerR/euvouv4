from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone

db = SQLAlchemy()

class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(20))
    senha_hash = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(20), default='comum')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

class Rifa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descricao_premio = db.Column(db.String(300), nullable=True)  
    valor_numero = db.Column(db.Float, nullable=False)
    data_inicio = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    data_fim = db.Column(db.DateTime, nullable=True)
    imagem_premio = db.Column(db.String(300), nullable=True)
    imagem_fundo = db.Column(db.String(300), nullable=True)
    limite_numeros = db.Column(db.Integer, nullable=True)
    id_organizador = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    status = db.Column(db.String(20), default='em_andamento')
    id_ficha_vencedora = db.Column(db.Integer, db.ForeignKey('ficha.id'), nullable=True)


class AutorizacaoCartela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_rifa = db.Column(db.Integer, db.ForeignKey('rifa.id'), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

class Cartela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_rifa = db.Column(db.Integer, db.ForeignKey('rifa.id'), nullable=False)
    numero_cartela = db.Column(db.Integer, nullable=False)
    id_usuario_criador = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    preco_individual = db.Column(db.Float, nullable=True)

class Ficha(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_cartela = db.Column(db.Integer, db.ForeignKey('cartela.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='disponivel')
    comprador_nome = db.Column(db.String(100), nullable=True)
    comprador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)
    data_criacao = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    valor_pago = db.Column(db.Float, nullable=True)

class Festa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    local = db.Column(db.String(200), nullable=False)
    descricao = db.Column(db.Text)
    valor_ingresso = db.Column(db.Float, nullable=False)
    imagem_fundo = db.Column(db.String(300), nullable=True)
    datas = db.relationship('DataFesta', backref='festa', cascade="all, delete-orphan")
    id_organizador = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    ingressos = db.relationship('Ingresso', backref='festa', cascade="all, delete-orphan")

class DataFesta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_festa = db.Column(db.Integer, db.ForeignKey('festa.id'), nullable=False)
    data = db.Column(db.Date, nullable=False)

    def __init__(self, id_festa, data):
        self.id_festa = id_festa
        self.data = data

class Ingresso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome_comprador = db.Column(db.String(100))
    data_utilizacao = db.Column(db.Date)
    festa_id = db.Column(db.Integer, db.ForeignKey('festa.id'))
    data_festa_id = db.Column(db.Integer, db.ForeignKey('data_festa.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    valor_pago = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default="vendido")
    criado_em = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    preco = db.Column(db.Float, nullable=False)


class AnalyticsEvent(db.Model):
    """Armazena eventos básicos de web analytics."""

    id = db.Column(db.Integer, primary_key=True)
    visitor_id = db.Column(db.String(40))
    path = db.Column(db.String(300))
    referrer = db.Column(db.String(300))
    event_type = db.Column(db.String(50))
    time_on_page = db.Column(db.Float, nullable=True)
    ad_id = db.Column(db.String(100), nullable=True)
    ip = db.Column(db.String(45))
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
