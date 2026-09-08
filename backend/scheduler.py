"""Agendador de lembretes de cobrança com APScheduler (doc oficial, seção 2.4).

Um job diário às 08h busca todas as vendas pendentes cuja data de cobrança
(due_date) seja igual à data atual e registra os IDs no Redis
(pending:reminders), para notificar o usuário responsável pela venda.
"""
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from cache import add_pending_reminder
from database import SessionLocal
from models.sale import Sale, SaleStatus


def check_due_charges() -> int:
    """Verifica cobranças que vencem hoje e registra lembretes. Retorna a contagem."""
    today = date.today()
    db = SessionLocal()
    try:
        sales = (
            db.query(Sale)
            .filter(
                Sale.status == SaleStatus.pending,
                Sale.due_date == today,
            )
            .all()
        )
    finally:
        db.close()

    for sale in sales:
        add_pending_reminder(sale.id)
    return len(sales)


scheduler = BackgroundScheduler(timezone="UTC")
scheduler.add_job(
    check_due_charges,
    CronTrigger(hour=8, minute=0),
    id="pending-reminders",
    replace_existing=True,
)
