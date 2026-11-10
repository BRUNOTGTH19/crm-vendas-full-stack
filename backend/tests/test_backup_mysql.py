"""Testes do backup lógico do MySQL (P0 da auditoria).

Não chamam o ``mysqldump`` real: o comando é injetado, então o teste cobre a
montagem dos argumentos, a validação do dump, a compressão e a retenção.
"""
from __future__ import annotations

import gzip
import sys
from datetime import datetime, timezone

import pytest

from backup_mysql import (
    BackupError,
    client_config,
    create_backup,
    dump_arguments,
    dump_filename,
    prune_backups,
)

VALID_DUMP = b"-- MySQL dump 10.13\n-- Host: db.example\nCREATE TABLE t (id INT);\n"


def _fake_dump(payload: bytes, exit_code: int = 0) -> list[str]:
    code = (
        "import sys; "
        f"sys.stdout.buffer.write({payload!r}); "
        f"sys.stderr.write('erro simulado'); sys.exit({exit_code})"
    )
    return [sys.executable, "-c", code]


def test_dump_filename_is_sortable_and_prefixed():
    name = dump_filename(datetime(2026, 11, 10, 12, 34, 56, tzinfo=timezone.utc))
    assert name == "crm-20261110-123456.sql.gz"


def test_dump_arguments_never_include_the_password():
    args = dump_arguments("/tmp/credenciais.cnf", "crm")
    assert "--defaults-extra-file=/tmp/credenciais.cnf" in args
    assert "crm" == args[-1]
    assert not any("senha" in arg or "password=" in arg for arg in args)


def test_client_config_keeps_password_only_in_the_file():
    from sqlalchemy.engine import make_url

    url = make_url("mysql+pymysql://user:senha@db.example:3306/crm")
    config = client_config(url)
    assert "host=db.example" in config
    assert "user=user" in config
    assert "password=senha" in config


def test_create_backup_writes_valid_gzip(tmp_path):
    target = create_backup(tmp_path, dump_cmd=_fake_dump(VALID_DUMP))

    assert target.exists()
    assert target.name.endswith(".sql.gz")
    with gzip.open(target, "rb") as handle:
        assert handle.read() == VALID_DUMP


def test_invalid_dump_is_rejected_and_not_kept(tmp_path):
    with pytest.raises(BackupError):
        create_backup(tmp_path, dump_cmd=_fake_dump(b"<html>erro</html>"))

    assert list(tmp_path.glob("crm-*.sql.gz")) == []


def test_mysqldump_failure_raises_without_partial_file(tmp_path):
    with pytest.raises(BackupError, match="mysqldump falhou"):
        create_backup(tmp_path, dump_cmd=_fake_dump(VALID_DUMP, exit_code=2))

    assert list(tmp_path.glob("crm-*")) == []


def test_prune_keeps_only_the_newest(tmp_path):
    for index in range(5):
        (tmp_path / f"crm-2026010{index}-000000.sql.gz").write_bytes(b"x")

    removed = prune_backups(tmp_path, keep=2)

    remaining = sorted(path.name for path in tmp_path.glob("crm-*.sql.gz"))
    assert remaining == ["crm-20260103-000000.sql.gz", "crm-20260104-000000.sql.gz"]
    assert len(removed) == 3


def test_create_backup_applies_retention(tmp_path):
    for index in range(3):
        (tmp_path / f"crm-2026010{index}-000000.sql.gz").write_bytes(b"x")

    create_backup(tmp_path, keep=2, dump_cmd=_fake_dump(VALID_DUMP))

    assert len(list(tmp_path.glob("crm-*.sql.gz"))) == 2
