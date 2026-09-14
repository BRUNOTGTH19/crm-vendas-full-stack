"""Cobrança personalizada + lembretes de vencimento (100% grátis).

Regras de negócio:
- A mensagem de cobrança é montada a partir de um template configurável
  (`settings.collection_message_template`) com os dados da venda e do cliente.
- O envio é feito por deep-link oficial do WhatsApp (``wa.me``), que abre o
  app/WhatsApp Web com a mensagem pronta. Não usa API paga nem automação
  não-oficial (que arrisca banimento do número).
- A lista de lembretes reaproveita o mesmo universo de vendas que o
  APScheduler marca em Redis (``pending:reminders``) e ainda inclui vendas
  já vencidas, para a central de cobranças funcionar mesmo sem o job diário.
"""
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import quote

from sqlalchemy.orm import Session

import cache
from config import settings
from models.client import Client
from models.sale import Sale, SaleStatus


def _fmt_money(value) -> str:
    """Formata Decimal/num em Real brasileiro: 1234.5 -> R$ 1.234,50."""
    number = Decimal(value or 0).quantize(Decimal("0.01"))
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "sem data definida"


def only_digits(phone: str | None) -> str | None:
    """Normaliza o telefone para o formato aceito pelo wa.me (só dígitos)."""
    if not phone:
        return None
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    return digits or None


def situation_of(due_date: date | None, today: date | None = None) -> str:
    """Classifica a cobrança em 'vencida', 'hoje' ou 'a-vencer'."""
    if not due_date:
        return "a-vencer"
    today = today or date.today()
    if due_date < today:
        return "vencida"
    if due_date == today:
        return "hoje"
    return "a-vencer"


_SITUATION_LINE = {
    "vencida": "⚠️ Situação: pagamento VENCIDO.\n",
    "hoje": "⏰ Situação: o vencimento é HOJE.\n",
    "a-vencer": "✅ Situação: dentro do prazo.\n",
}


def build_message(client_name: str, sale: Sale, situation: str) -> str:
    """Monta a mensagem personalizada a partir do template configurável."""
    amount = sale.remaining if sale.remaining is not None else sale.total
    try:
        return settings.collection_message_template.format(
            cliente=client_name or "cliente",
            venda=sale.id,
            valor=_fmt_money(amount),
            vencimento=_fmt_date(sale.due_date),
            situacao=_SITUATION_LINE.get(situation, ""),
            empresa=settings.company_name,
        )
    except (KeyError, IndexError, ValueError):
        # Template do .env inválido: cai para um texto seguro.
        return (
            f"Olá {client_name or 'cliente'}! Passando para lembrar do pagamento "
            f"da venda #{sale.id} no valor de {_fmt_money(amount)}"
            f" (vencimento {_fmt_date(sale.due_date)}). Obrigado!"
        )


def build_whatsapp_link(phone: str | None, message: str) -> str | None:
    """Gera o deep-link gratuito wa.me com a mensagem já preenchida."""
    digits = only_digits(phone)
    if not digits:
        return None
    return f"https://wa.me/{digits}?text={quote(message)}"


def build_collection_message(db: Session, sale: Sale) -> dict:
    """Retorna o payload completo de cobrança de uma venda."""
    client = db.query(Client).filter(Client.id == sale.client_id).first()
    client_name = client.full_name if client else f"Cliente {sale.client_id}"
    phone = client.whatsapp if client else None
    digits = only_digits(phone)
    situation = situation_of(sale.due_date)
    amount = sale.remaining if sale.remaining is not None else sale.total
    message = build_message(client_name, sale, situation)
    return {
        "sale_id": sale.id,
        "client_id": sale.client_id,
        "client_name": client_name,
        "whatsapp": phone,
        "whatsapp_digits": digits,
        "has_phone": digits is not None,
        "amount": amount,
        "due_date": sale.due_date,
        "situation": situation,
        "message": message,
        "wa_link": build_whatsapp_link(phone, message),
    }


def list_due_reminders(db: Session) -> list[dict]:
    """Lista cobranças que vencem hoje ou já venceram.

    Une as vendas pendentes com ``due_date <= hoje`` ao conjunto marcado pelo
    agendador em ``pending:reminders`` (assim, mesmo uma cobrança futura marcada
    manualmente aparece na central). Ordenadas por vencimento mais antigo.
    """
    today = date.today()
    horizon = today + timedelta(days=0)

    sales = (
        db.query(Sale)
        .filter(
            Sale.status == SaleStatus.pending,
            Sale.due_date.isnot(None),
            Sale.due_date <= horizon,
        )
        .order_by(Sale.due_date.asc(), Sale.id.asc())
        .all()
    )

    scheduled_ids = cache.get_pending_reminders()
    reminders: list[dict] = []
    seen: set[int] = set()

    for sale in sales:
        client = db.query(Client).filter(Client.id == sale.client_id).first()
        reminders.append(
            {
                "sale_id": sale.id,
                "client_id": sale.client_id,
                "client_name": client.full_name if client else f"Cliente {sale.client_id}",
                "whatsapp": client.whatsapp if client else None,
                "situation": situation_of(sale.due_date, today),
                "amount": sale.remaining if sale.remaining is not None else sale.total,
                "due_date": sale.due_date,
                "scheduled": sale.id in scheduled_ids,
            }
        )
        seen.add(sale.id)

    # Vendas marcadas pelo agendador que não caíram no filtro acima (ex.: data
    # futura marcada manualmente) também entram na lista.
    extra_ids = scheduled_ids - seen
    if extra_ids:
        extras = (
            db.query(Sale)
            .filter(Sale.id.in_(extra_ids), Sale.status == SaleStatus.pending)
            .all()
        )
        for sale in extras:
            client = db.query(Client).filter(Client.id == sale.client_id).first()
            reminders.append(
                {
                    "sale_id": sale.id,
                    "client_id": sale.client_id,
                    "client_name": client.full_name if client else f"Cliente {sale.client_id}",
                    "whatsapp": client.whatsapp if client else None,
                    "situation": situation_of(sale.due_date, today),
                    "amount": sale.remaining if sale.remaining is not None else sale.total,
                    "due_date": sale.due_date,
                    "scheduled": True,
                }
            )

    return reminders