"""Envio do e-mail de recuperação de senha (self-service).

Sem SMTP configurado o serviço fica inerte: ``is_email_configured`` devolve
``False`` e a tela de login oferece o fluxo por token do administrador, que já
existe e não depende de provedor externo.

Decisões de segurança:

- as credenciais vêm apenas do ambiente (Render), nunca do banco nem do
  repositório;
- o token aparece só no corpo da mensagem, nunca em log;
- falha de SMTP não derruba a requisição: o endpoint responde genérico e o
  administrador ainda pode gerar o token pelo painel;
- o remetente é obrigatório para evitar mensagens sem ``From`` válido.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from config import settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 10


def is_email_configured() -> bool:
    """Há SMTP e remetente suficientes para entregar o link?"""
    return bool((settings.smtp_host or "").strip() and (settings.smtp_from or "").strip())


def reset_link(token: str) -> str:
    """Link para a tela de confirmação (vazio se a URL pública não foi definida)."""
    base = (settings.app_public_url or "").strip().rstrip("/")
    if not base:
        return ""
    return f"{base}/#/reset-password?token={token}"


def send_password_reset_email(to: str, token: str, expires_minutes: int) -> bool:
    """Envia o token por e-mail. Devolve ``False`` se não foi possível."""
    if not is_email_configured():
        logger.warning("password_reset_email_skipped sem_smtp")
        return False

    link = reset_link(token)
    message = EmailMessage()
    message["Subject"] = "Redefinição de senha - CRM Vendas"
    message["From"] = settings.smtp_from
    message["To"] = to
    instructions = (
        "Recebemos um pedido para redefinir a senha da sua conta no CRM Vendas.\n\n"
    )
    if link:
        instructions += (
            f"Abra o link para escolher a nova senha (vale por {expires_minutes} minutos):\n"
            f"{link}\n\n"
        )
    instructions += (
        "Se o link não funcionar, use o token abaixo em \"Tenho um token de redefinição\":\n"
        f"{token}\n\n"
        "Se você não pediu a redefinição, ignore esta mensagem: a senha atual continua valendo."
    )
    message.set_content(instructions)

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        # Só o tipo do erro: endereço e token não vão para o log.
        logger.warning("password_reset_email_failed error=%s", type(exc).__name__)
        return False

    logger.info("password_reset_email_sent")
    return True
