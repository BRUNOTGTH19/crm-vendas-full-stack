"""Fonte única de "agora"/"hoje" do backend (fuso de referência do aplicativo).

O servidor de produção roda em **UTC**, mas o negócio acontece no fuso do
usuário. Usar ``date.today()`` (fuso do servidor) fazia o CRM discordar de si
mesmo: entre 21h e 23h59 de Brasília a API já considerava "amanhã", então

- uma cobrança que vence hoje aparecia como **VENCIDA** na API e como
  **"Vence hoje"** na tela (o frontend recalcula com a data local do navegador);
- ``overdue_count`` do painel divergia da lista de cobranças;
- o push de nova venda com ``due_date <= hoje`` disparava com o dia deslocado.

``REMINDER_TIMEZONE`` passa a ser o **fuso de referência do aplicativo**: além
de agendar os lembretes, define o que é "hoje" no painel, nas cobranças e nos
relatórios. Todo módulo deve usar estas funções em vez de ``date.today()``.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import settings


def local_now() -> datetime:
    """Agora, no fuso de referência do aplicativo."""
    return datetime.now(ZoneInfo(settings.reminder_timezone))


def local_today() -> date:
    """Data de hoje, no fuso de referência do aplicativo."""
    return local_now().date()
