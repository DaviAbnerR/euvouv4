from app import db
from datetime import datetime, timedelta, timezone
from models import Usuario, Rifa, Festa, Cartela, Ficha, AnalyticsEvent
import json


def create_user(email='user@example.com', password='123', tipo='organizador'):
    user = Usuario(nome='User', email=email, tipo=tipo)
    user.set_senha(password)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, email, senha):
    return client.post('/login', data={'email': email, 'senha': senha})


def test_login_success(client):
    with client.application.app_context():
        user = create_user()
    resp = login(client, 'user@example.com', '123')
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert sess['usuario_id'] == user.id


def test_criar_rifa(client):
    with client.application.app_context():
        user = create_user()
    login(client, 'user@example.com', '123')
    data = {
        'titulo': 'Rifa Teste',
        'descricao_premio': 'Premio',
        'valor_numero': 10,
        'data_inicio': '2023-01-01',
        'data_fim': '2023-12-31',
        'limite_numeros': 50
    }
    resp = client.post('/api/rifa/criar', data=json.dumps(data),
                       content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
    with client.application.app_context():
        assert Rifa.query.filter_by(titulo='Rifa Teste').first() is not None


def test_criar_festa(client):
    with client.application.app_context():
        user = create_user()
    login(client, 'user@example.com', '123')
    data = {
        'nome': 'Festa Teste',
        'local': 'Local',
        'valor_ingresso': 15,
        'descricao': 'Desc',
        'datas': ['2023-01-01']
    }
    resp = client.post('/api/festa/criar', data=json.dumps(data),
                       content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
    with client.application.app_context():
        assert Festa.query.filter_by(nome='Festa Teste').first() is not None


def test_sortear_rifa(client):
    with client.application.app_context():
        user = create_user()
        rifa = Rifa(
            titulo='Rifa Sorteio',
            valor_numero=5,
            data_fim=datetime.now(timezone.utc) - timedelta(days=1),
            id_organizador=user.id
        )
        db.session.add(rifa)
        db.session.commit()

        cartela = Cartela(id_rifa=rifa.id, numero_cartela=1, id_usuario_criador=user.id)
        db.session.add(cartela)
        db.session.commit()

        ficha = Ficha(
            id_cartela=cartela.id,
            numero=1,
            status='vendido',
            comprador_nome='Comprador',
            comprador_id=user.id,
            valor_pago=5
        )
        db.session.add(ficha)
        db.session.commit()

        rifa_id = rifa.id
        ficha_id = ficha.id

    login(client, 'user@example.com', '123')
    resp = client.post(f'/api/rifa/{rifa_id}/sortear')
    assert resp.status_code == 200
    assert resp.get_json()['ok'] is True
    with client.application.app_context():
        rifa_atualizada = db.session.get(Rifa, rifa_id)
        assert rifa_atualizada.id_ficha_vencedora == ficha_id


def test_analytics_endpoint(client):
    data = {
        'type': 'pageview',
        'path': '/',
        'referrer': '',
        'visitor_id': 'test'
    }
    resp = client.post('/api/analytics', data=json.dumps(data),
                       content_type='application/json')
    assert resp.status_code == 200
    with client.application.app_context():
        assert AnalyticsEvent.query.count() == 1


def test_bot_detection(client):
    data = {
        'type': 'pageview',
        'path': '/',
        'referrer': '',
        'visitor_id': 'bot'
    }
    # excede o limite definido em BOT_EVENT_LIMIT
    for _ in range(51):
        resp = client.post('/api/analytics', data=json.dumps(data),
                           content_type='application/json')
    assert resp.status_code == 429
    with client.application.app_context():
        # Apenas os 50 primeiros devem ser registrados
        assert AnalyticsEvent.query.count() == 50


def test_relatorio_anuncio(client):
    with client.application.app_context():
        db.session.add_all([
            AnalyticsEvent(event_type='ad_impression', ad_id='ad1', visitor_id='v1'),
            AnalyticsEvent(event_type='ad_impression', ad_id='ad1', visitor_id='v2'),
            AnalyticsEvent(event_type='ad_click', ad_id='ad1', visitor_id='v1'),
        ])
        db.session.commit()
    resp = client.get('/api/relatorio/anuncio/ad1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['impressoes'] == 2
    assert data['cliques'] == 1
    assert data['visualizacoes'] == 2
    assert data['ctr'] == 50.0
