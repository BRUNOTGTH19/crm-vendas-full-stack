"""A17: rate limit compartilhado no Redis e lock diário do scheduler.

O Redis é simulado (sem servidor real): os testes cobrem a semântica das
janelas, a queda para memória quando o Redis falha e o ``SET NX`` do lembrete.
"""
from __future__ import annotations

import redis

import scheduler
from config import settings
from middleware import rate_limit


class FakeRedis:
    """Subconjunto de sorted sets usado pelo rate limit."""

    def __init__(self) -> None:
        self.zsets: dict[str, dict[str, float]] = {}
        self.expires: dict[str, int] = {}

    def zremrangebyscore(self, key, low, high):
        items = self.zsets.get(key, {})
        for member, score in list(items.items()):
            if low <= score <= high:
                del items[member]
        return 0

    def zcard(self, key):
        return len(self.zsets.get(key, {}))

    def zadd(self, key, mapping):
        self.zsets.setdefault(key, {}).update(mapping)
        return 1

    def expire(self, key, seconds):
        self.expires[key] = seconds
        return True

    def scan_iter(self, match=None):
        prefix = (match or "").rstrip("*")
        return [key for key in list(self.zsets) if key.startswith(prefix)]

    def delete(self, *keys):
        for key in keys:
            self.zsets.pop(key, None)
        return len(keys)


class BrokenRedis:
    """Redis que sempre falha, para validar o fallback."""

    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise redis.RedisError("indisponível")
        return fail


def _use_redis(monkeypatch, fake):
    monkeypatch.setattr(settings, "rate_limit_backend", "redis")
    monkeypatch.setattr(rate_limit, "redis_client", fake)
    rate_limit.reset_rate_limit()


def test_redis_backend_counts_across_instances(monkeypatch):
    fake = FakeRedis()
    _use_redis(monkeypatch, fake)
    now = 1_000.0

    for _ in range(rate_limit.LOGIN_MAX_FAILURES - 1):
        rate_limit.record_login_failure("1.2.3.4", now=now)

    assert rate_limit.is_login_blocked("1.2.3.4", now=now) is False
    rate_limit.record_login_failure("1.2.3.4", now=now)
    assert rate_limit.is_login_blocked("1.2.3.4", now=now) is True
    # O contador saiu do processo: a memória local ficou intocada.
    assert rate_limit._failures == {}
    assert any(key.startswith(rate_limit.REDIS_PREFIX) for key in fake.zsets)
    assert fake.expires


def test_redis_backend_forgets_events_outside_the_window(monkeypatch):
    fake = FakeRedis()
    _use_redis(monkeypatch, fake)

    for _ in range(rate_limit.LOGIN_MAX_FAILURES):
        rate_limit.record_login_failure("1.2.3.4", now=1_000.0)

    later = 1_000.0 + rate_limit.LOGIN_WINDOW_SECONDS + 1
    assert rate_limit.is_login_blocked("1.2.3.4", now=later) is False


def test_redis_failure_falls_back_to_memory(monkeypatch):
    _use_redis(monkeypatch, BrokenRedis())

    for _ in range(rate_limit.LOGIN_MAX_FAILURES):
        rate_limit.record_login_failure("5.6.7.8", now=10.0)

    assert len(rate_limit._failures["5.6.7.8"]) == rate_limit.LOGIN_MAX_FAILURES
    assert rate_limit.is_login_blocked("5.6.7.8", now=10.0) is True


def test_reset_clears_redis_keys(monkeypatch):
    fake = FakeRedis()
    _use_redis(monkeypatch, fake)
    rate_limit.record_login_failure("1.2.3.4", now=10.0)

    rate_limit.reset_rate_limit()

    assert fake.zsets == {}


def test_memory_backend_ignores_redis(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(rate_limit, "redis_client", BrokenRedis())
    rate_limit.reset_rate_limit()

    rate_limit.record_ai_message("user:1", now=5.0)
    assert rate_limit.is_ai_blocked("user:1", now=5.0) is False


class FakeSetRedis:
    def __init__(self, claimed):
        self.claimed = claimed
        self.calls = []

    def set(self, key, value, nx=False, ex=None):
        self.calls.append((key, value, nx, ex))
        return self.claimed


def test_daily_lock_uses_set_nx_with_ttl(monkeypatch):
    fake = FakeSetRedis(claimed=True)
    monkeypatch.setattr("redis_client.redis_client", fake)

    assert scheduler._claim_daily_run("2026-11-10") is True
    key, _, nx, ex = fake.calls[0]
    assert key == "reminder:lock:2026-11-10"
    assert nx is True
    assert ex == scheduler.REMINDER_LOCK_TTL_SECONDS


def test_daily_lock_reports_already_claimed(monkeypatch):
    monkeypatch.setattr("redis_client.redis_client", FakeSetRedis(claimed=None))
    assert scheduler._claim_daily_run("2026-11-10") is False


def test_daily_lock_allows_run_when_redis_is_down(monkeypatch):
    monkeypatch.setattr("redis_client.redis_client", BrokenRedis())
    assert scheduler._claim_daily_run("2026-11-10") is True


def test_scheduled_run_is_skipped_when_already_claimed(monkeypatch):
    monkeypatch.setattr(scheduler, "_claim_daily_run", lambda day: False)

    result = scheduler.run_due_charges()

    assert result["skipped"] == "already_ran_today"
    assert result["sales_found"] == 0


def test_manual_and_preview_runs_bypass_daily_lock(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        scheduler, "_claim_daily_run", lambda day: calls.append(day) or True
    )

    scheduler.run_due_charges(user_id=1, dry_run=False, source="manual")
    scheduler.run_due_charges(dry_run=True)
    assert calls == []

    scheduler.run_due_charges()
    assert len(calls) == 1
