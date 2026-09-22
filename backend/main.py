import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from config import settings
from routers import (
    admin,
    auth,
    clients,
    collections,
    dashboard,
    payments,
    push,
    queue,
    reports,
    sales,
)
from scheduler import scheduler as reminder_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicia o APScheduler de lembretes ao subir e encerra ao desligar (doc 2.4)."""
    reminder_scheduler.start()
    job = reminder_scheduler.get_job("pending-reminders")
    logging.getLogger(__name__).info(
        "reminder_scheduler_started timezone=%s days_before=%s trigger=%s next_run=%s",
        settings.reminder_timezone, settings.reminder_days_before, job.trigger,
        getattr(job, "next_run_time", None),
    )
    yield
    reminder_scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# CORS: a autenticação usa token Bearer (header Authorization), NÃO cookies.
# Por isso `allow_credentials=False` — combinar "*" com credenciais é uma
# configuração rejeitada por navegadores e um risco de segurança. As origens
# podem ser restringidas via CORS_ALLOW_ORIGINS (lista separada por vírgula).
_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def force_utf8_json_charset(request: Request, call_next) -> Response:
    """Garante `charset=utf-8` explícito nas respostas JSON.

    O JSON já é UTF-8 por definição (RFC 8259), mas declarar o charset
    evita que clientes que adivinham o encoding (ex.: PowerShell, que
    assume latin-1 quando ausente) quebrem os emojis da mensagem de
    cobrança. Não altera respostas binárias (ex.: download do PDF).
    """
    response = await call_next(request)
    content_type = response.headers.get("content-type", "")
    if content_type.split(";")[0].strip().lower() == "application/json":
        response.headers["content-type"] = "application/json; charset=utf-8"
    return response

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(sales.router)
app.include_router(dashboard.router)
app.include_router(queue.router)
app.include_router(reports.router)
app.include_router(payments.router)
app.include_router(collections.router)
app.include_router(push.router)
app.include_router(admin.router)


@app.get("/")
def root():
    return {"status": "ok", "app": settings.app_name}


@app.get("/health")
def health_check():
    return {"status": "healthy"}