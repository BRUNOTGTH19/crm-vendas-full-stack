"""Helpers de cache Redis (doc oficial, seção 4.2).

Chaves:
- dashboard:{ano-mes}      → métricas do dashboard (TTL 5 min)
- sales:client:{id}        → histórico de vendas do cliente (TTL 2 min)
- pending:reminders        → IDs de vendas pendentes para lembrete (sem expiração)
"""
import json

import redis

from redis_client import redis_client

DASHBOARD_TTL = 300  # 5 minutos
CLIENT_SALES_TTL = 120  # 2 minutos
PENDING_REMINDERS_KEY = "pending:reminders"


def get_json(key: str):
    """Retorna o valor em JSON da chave, ou None se ausente/erro."""
    try:
        cached = redis_client.get(key)
    except redis.RedisError:
        return None
    if not cached:
        return None
    try:
        return json.loads(cached)
    except (ValueError, TypeError):
        return None


def set_json(key: str, data, ttl: int) -> None:
    try:
        redis_client.set(key, json.dumps(data, default=str), ex=ttl)
    except redis.RedisError:
        pass  # cache é best-effort


def delete_key(key: str) -> None:
    try:
        redis_client.delete(key)
    except redis.RedisError:
        pass


def delete_pattern(pattern: str) -> None:
    try:
        keys = list(redis_client.scan_iter(pattern))
        if keys:
            redis_client.delete(*keys)
    except redis.RedisError:
        pass


def invalidate_dashboard_cache() -> None:
    delete_pattern("dashboard:*")


def invalidate_client_sales_cache(client_id: int) -> None:
    delete_key(f"sales:client:{client_id}")


def add_pending_reminder(sale_id: int) -> None:
    try:
        redis_client.sadd(PENDING_REMINDERS_KEY, sale_id)
    except redis.RedisError:
        pass


def get_pending_reminders() -> set[int]:
    try:
        return {int(v) for v in redis_client.smembers(PENDING_REMINDERS_KEY)}
    except redis.RedisError:
        return set()
