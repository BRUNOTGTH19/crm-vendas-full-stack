"""Agendador de lembretes de cobrança com APScheduler (doc oficial, seção 2.4).

Um job diário às 08h busca todas as vendas pendentes cuja data de cobrança
(due_date) vence hoje OU já venceu e registra os IDs no Redis
(pending:reminders), para notificar o usuário responsável pela venda.

Esses IDs alimentam a central de cobranças (``GET /collections/reminders``),
que monta a mensagem personalizada de cobrança pronta para envio no WhatsApp.
"""
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from cache import add_pending_reminder
from database import SessionLocal
from models.sale import Sale, SaleStatus
from services.push_service import send_push_to_all


def check_due_charges() -> int:
    """Verifica cobranças vencidas ou que vencem hoje e registra lembretes.

    Retorna a quantidade de vendas sinalizadas.
    """
    today = date.today()
    db = SessionLocal()
    try:
        sales = (
            db.query(Sale)
            .filter(
                Sale.status == SaleStatus.pending,
                Sale.due_date.isnot(None),
                Sale.due_date <= today,
            )
            .all()
        )
    finally:
        db.close()

    for sale in sales:
        add_pending_reminder(sale.id)

    # Envia push notification para os dispositivos inscritos (Web Push).
    if sales:
        db_push = SessionLocal()
        try:
            send_push_to_all(
                db_push,
                title="🔔 Alerta de cobranças",
                body=(
                    f"{len(sales)} cobrança(s) vencida(s) ou vencendo hoje. "
                    "Abra o app para ver os detalhes."
                ),
                url="/#/queue",
            )
        finally:
            db_push.close()

    return len(sales)


scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(
    check_due_charges,
    CronTrigger(hour=8, minute=0),
    id="pending-reminders",
    replace_existing=True,
)
