from datetime import datetime, timezone

from flask.cli import with_appcontext

from app import app, db, sortear_rifa
from models import Rifa

@app.cli.command('verificar_rifas')
@with_appcontext
def verificar_rifas():
    """Finaliza rifas expiradas e registra vencedores."""
    agora = datetime.now(timezone.utc)
    rifas = Rifa.query.filter(
        Rifa.status == 'em_andamento',
        Rifa.data_fim != None,
        Rifa.data_fim <= agora
    ).all()
    for rifa in rifas:
        ficha_vencedora = sortear_rifa(rifa)
        if ficha_vencedora:
            app.logger.info(
                'Rifa %s finalizada. Vencedor ficha %s',
                rifa.id,
                ficha_vencedora.id,
            )
        else:
            app.logger.info('Rifa %s finalizada sem fichas vendidas', rifa.id)

