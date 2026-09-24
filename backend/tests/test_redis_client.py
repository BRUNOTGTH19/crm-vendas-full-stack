"""Regressão: cliente Redis sem TLS não pode receber ``ssl_cert_reqs``.

Em URL ``redis://`` (sem TLS, como no ambiente local) a redis-py rejeita o
argumento com ``TypeError``. O ``queue_service`` montava o cliente por conta
própria passando ``ssl_cert_reqs="required"``, então ``POST /queue/pdf/{id}``
respondia **500** e nenhum recibo em PDF era emitido fora de produção.

O ``ssl_cert_reqs`` só pode existir em ``rediss://`` — exatamente o que a
fábrica compartilhada ``build_redis_client`` garante.
"""
from services import queue_service
from redis_client import build_redis_client

# Avaliado na importação do módulo, antes de o conftest substituir
# ``queue_service.redis_client`` por um mock.
QUEUE_CLIENT_KWARGS = dict(queue_service.redis_client.connection_pool.connection_kwargs)


def test_build_redis_client_without_ssl_kwargs(monkeypatch):
    """Fábrica cria o cliente sem ``ssl_cert_reqs`` quando não há TLS."""
    import redis_client as redis_client_module

    monkeypatch.setattr(redis_client_module, "_ssl_kwargs", {})
    created = redis_client_module.build_redis_client(decode_responses=False)
    kwargs = created.connection_pool.connection_kwargs
    assert kwargs.get("ssl_cert_reqs") is None
    assert kwargs["decode_responses"] is False


def test_build_redis_client_keeps_bytes_decoding_for_pdf_jobs():
    created = build_redis_client(decode_responses=False)
    assert created.connection_pool.connection_kwargs["decode_responses"] is False


def test_queue_service_client_is_built_without_ssl_for_plain_redis():
    """O cliente da fila de PDFs não carrega ``ssl_cert_reqs`` em ``redis://``."""
    assert QUEUE_CLIENT_KWARGS.get("ssl_cert_reqs") is None
    assert QUEUE_CLIENT_KWARGS["decode_responses"] is False
