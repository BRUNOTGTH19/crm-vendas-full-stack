"""Lembretes diários: pendentes com vencimento até hoje + antecedência configurada."""
import logging
from collections import Counter
from datetime import datetime, timedelta
from threading import Lock
from uuid import uuid4
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from cache import add_pending_reminder
from config import settings
from database import SessionLocal
from models.sale import Sale, SaleStatus
from services.push_service import send_push_to_all

logger = logging.getLogger(__name__)
_run_lock = Lock()


class ReminderJobBusy(Exception):
    """Há uma execução no mesmo processo em andamento."""


def run_due_charges(*, user_id: int | None = None, dry_run: bool = False,
                    source: str = "scheduled", run_id: str | None = None) -> dict:
    """Executa a mesma regra para cron e admin. Aceitação não prova entrega física."""
    if not _run_lock.acquire(blocking=False):
        raise ReminderJobBusy()
    run_id = run_id or uuid4().hex
    try:
        today = datetime.now(ZoneInfo(settings.reminder_timezone)).date()
        cutoff = today + timedelta(days=settings.reminder_days_before)
        result = {
            "run_id": run_id, "source": source, "dry_run": dry_run,
            "date": today.isoformat(), "cutoff": cutoff.isoformat(),
            "timezone": settings.reminder_timezone, "sales_found": 0,
            "users_found": 0, "push_accepted": 0, "users_failed": 0,
        }
        logger.info("reminder_started run_id=%s source=%s dry_run=%s user_id=%s cutoff=%s timezone=%s",
                    run_id, source, dry_run, user_id, cutoff, settings.reminder_timezone)
        with SessionLocal() as db:
            query = db.query(Sale.id, Sale.user_id).filter(
                Sale.status == SaleStatus.pending,
                Sale.due_date.isnot(None), Sale.due_date <= cutoff,
            )
            if user_id is not None:
                query = query.filter(Sale.user_id == user_id)
            sales = query.all()
        owners = Counter(owner_id for _, owner_id in sales)
        result.update(sales_found=len(sales), users_found=len(owners))
        logger.info("reminder_found run_id=%s sales=%d users=%d", run_id, len(sales), len(owners))
        if not dry_run:
            for sale_id, _ in sales:
                add_pending_reminder(sale_id)
            for owner_id, count in owners.items():
                logger.info("reminder_notify run_id=%s user_id=%s sales=%d", run_id, owner_id, count)
                try:
                    with SessionLocal() as db:
                        accepted = send_push_to_all(
                            db, title="🔔 Alerta de cobranças",
                            body=f"{count} cobrança(s) com vencimento até {cutoff:%d/%m/%Y}. Abra o app para ver os detalhes.",
                            url="/#/queue", user_id=owner_id, run_id=run_id,
                        )
                    result["push_accepted"] += accepted
                except Exception as exc:
                    result["users_failed"] += 1
                    logger.warning("reminder_user_failed run_id=%s user_id=%s error_type=%s",
                                   run_id, owner_id, type(exc).__name__)
        logger.info("reminder_finished run_id=%s sales=%d push_accepted=%d users_failed=%d dry_run=%s",
                    run_id, len(sales), result["push_accepted"], result["users_failed"], dry_run)
        return result
    except Exception as exc:
        logger.error("reminder_failed run_id=%s error_type=%s", run_id, type(exc).__name__)
        raise
    finally:
        _run_lock.release()


def check_due_charges() -> int:
    """Entrada do APScheduler; preserva retorno da quantidade de vendas."""
    return run_due_charges()["sales_found"]


scheduler = BackgroundScheduler(timezone=settings.reminder_timezone)
scheduler.add_job(
    check_due_charges,
    CronTrigger(hour=settings.reminder_hour, minute=0, timezone=settings.reminder_timezone),
    id="pending-reminders", replace_existing=True,
    max_instances=1, coalesce=True, misfire_grace_time=3600,
)
