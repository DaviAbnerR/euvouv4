import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import pytest
from app import app, db, recent_events, blocked_ips

@pytest.fixture
def client():
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()
        recent_events.clear()
        blocked_ips.clear()

