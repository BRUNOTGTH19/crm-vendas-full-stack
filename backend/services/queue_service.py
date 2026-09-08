"""Fila de geração de PDFs usando Redis."""
import base64
import uuid
from datetime import datetime, timezone

import redis

from config import settings
from database import SessionLocal
from models.client import Client
from models.sale import Sale
from services.pdf_service import generate_invoice_pdf

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=False)

JOB_TTL_SECONDS = 3600  # jobs e PDFs expiram em 1 hora


def _job_key(job_id: str) -> str:
    return f"pdf_job:{job_id}"


def _pdf_key(job_id: str) -> str:
    return f"pdf_file:{job_id}"


def enqueue_pdf_job(sale_id: int) -> str:
    """Cria um job pendente para gerar o PDF de uma venda. Retorna o job_id."""
    db = SessionLocal()
    try:
        sale = db.query(Sale).filter(Sale.id == sale_id).first()
        if not sale:
            raise ValueError("Venda não encontrada")
    finally:
        db.close()

    job_id = uuid.uuid4().hex
    redis_client.hset(
        _job_key(job_id),
        mapping={
            "sale_id": sale_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    redis_client.expire(_job_key(job_id), JOB_TTL_SECONDS)
    return job_id


def process_pdf_job(job_id: str) -> None:
    """Gera o PDF da venda e armazena no Redis. Atualiza o status do job."""
    data = redis_client.hgetall(_job_key(job_id))
    if not data:
        return
    sale_id = int(data[b"sale_id"])
    try:
        db = SessionLocal()
        try:
            sale = db.query(Sale).filter(Sale.id == sale_id).first()
            if not sale:
                raise ValueError("Venda não encontrada")
            client = db.query(Client).filter(Client.id == sale.client_id).first()
            pdf_bytes = generate_invoice_pdf(sale, client)
        finally:
            db.close()

        redis_client.set(_pdf_key(job_id), base64.b64encode(pdf_bytes))
        redis_client.expire(_pdf_key(job_id), JOB_TTL_SECONDS)
        redis_client.hset(_job_key(job_id), "status", "done")
        redis_client.expire(_job_key(job_id), JOB_TTL_SECONDS)
    except Exception as exc:
        redis_client.hset(
            _job_key(job_id),
            mapping={"status": "error", "error": str(exc)},
        )
        redis_client.expire(_job_key(job_id), JOB_TTL_SECONDS)


def get_job_status(job_id: str) -> dict | None:
    data = redis_client.hgetall(_job_key(job_id))
    if not data:
        return None
    return {
        "job_id": job_id,
        "sale_id": int(data[b"sale_id"]),
        "status": data[b"status"].decode(),
        "error": data[b"error"].decode() if b"error" in data else None,
        "created_at": data[b"created_at"].decode(),
    }


def get_pdf_bytes(job_id: str) -> bytes | None:
    data = redis_client.get(_pdf_key(job_id))
    if not data:
        return None
    return base64.b64decode(data)

