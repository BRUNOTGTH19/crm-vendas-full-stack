"""Testes da restauração do backup MySQL (P0 da auditoria).

Não chamam o ``mysql`` nem o banco real: o comando e a contagem de tabelas são
injetados, então o teste cobre a validação do dump, a recusa de destino
perigoso, o streaming para o cliente e o ``--drop`` só do banco criado aqui.
"""
from __future__ import annotations

import gzip
import sys

import pytest

import restore_mysql
from restore_mysql import (
    RestoreError,
    ensure_not_source,
    restore_arguments,
    restore_dump,
    validate_database_name,
)

VALID_DUMP = b"-- MySQL dump 10.13\n-- Host: db.example\nCREATE TABLE t (id INT);\n"
SOURCE = "mysql+pymysql://user:senha@db.example:3306/crm"


def _dump(tmp_path, payload: bytes = VALID_DUMP):
    path = tmp_path / "crm-20261110-030000.sql.gz"
    with gzip.open(path, "wb") as handle:
        handle.write(payload)
    return path


def _consumer(target=None, exit_code: int = 0, stderr: str = "") -> list[str]:
    code = "import sys; data = sys.stdin.buffer.read()"
    if target is not None:
        code += f"; open({str(target)!r}, 'wb').write(data)"
    code += f"; sys.stderr.write({stderr!r}); sys.exit({exit_code})"
    return [sys.executable, "-c", code]


def test_database_name_rejects_sql_injection():
    with pytest.raises(RestoreError, match="inválido"):
        validate_database_name("crm; DROP DATABASE producao")
    with pytest.raises(RestoreError):
        validate_database_name("")
    assert validate_database_name("crm_restore_check_1") == "crm_restore_check_1"


def test_restore_arguments_keep_password_out_of_argv():
    args = restore_arguments("/tmp/credenciais.cnf", "crm_restore_check")
    assert args[-1] == "crm_restore_check"
    assert not any("senha" in arg or "password=" in arg for arg in args)


def test_refuses_to_restore_over_the_source_database(tmp_path):
    dump = _dump(tmp_path)

    with pytest.raises(RestoreError, match="mesmo da DATABASE_URL"):
        restore_dump(dump, "crm", database_url=SOURCE, mysql_cmd=_consumer())

    ensure_not_source("crm_restore_check", SOURCE)  # não levanta


def test_drop_requires_create(tmp_path):
    with pytest.raises(RestoreError, match="exige --create"):
        restore_dump(
            _dump(tmp_path),
            "crm_restore_check",
            database_url=SOURCE,
            drop_after=True,
            mysql_cmd=_consumer(),
        )


def test_missing_dump_is_reported(tmp_path):
    with pytest.raises(RestoreError, match="não encontrado"):
        restore_dump(tmp_path / "nao-existe.sql.gz", "crm_restore_check")


def test_invalid_dump_is_rejected_before_calling_mysql(tmp_path):
    marker = tmp_path / "mysql-rodou"
    dump = _dump(tmp_path, b"<html>erro</html>")

    with pytest.raises(RestoreError, match="cabeçalho"):
        restore_dump(
            dump,
            "crm_restore_check",
            database_url=SOURCE,
            mysql_cmd=_consumer(marker),
        )

    assert not marker.exists()


def test_restore_streams_the_dump_and_reports_tables(tmp_path):
    received = tmp_path / "recebido.sql"
    dump = _dump(tmp_path)

    result = restore_dump(
        dump,
        "crm_restore_check",
        database_url=SOURCE,
        mysql_cmd=_consumer(received),
        count_fn=lambda: 12,
    )

    assert received.read_bytes() == VALID_DUMP
    assert result.tables == 12
    assert result.dropped is False


def test_mysql_failure_surfaces_the_error(tmp_path):
    with pytest.raises(RestoreError, match="mysql falhou"):
        restore_dump(
            _dump(tmp_path),
            "crm_restore_check",
            database_url=SOURCE,
            mysql_cmd=_consumer(exit_code=2, stderr="ERROR 1045: access denied"),
            count_fn=lambda: 0,
        )


def test_drop_only_removes_the_database_created_here(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        restore_mysql,
        "create_database",
        lambda url, database: calls.append(("create", database)),
    )
    monkeypatch.setattr(
        restore_mysql,
        "drop_database",
        lambda url, database: calls.append(("drop", database)),
    )

    result = restore_dump(
        _dump(tmp_path),
        "crm_restore_check",
        database_url=SOURCE,
        create=True,
        drop_after=True,
        mysql_cmd=_consumer(),
        count_fn=lambda: 4,
    )

    assert calls == [("create", "crm_restore_check"), ("drop", "crm_restore_check")]
    assert result.dropped is True


def test_compare_fails_when_restore_has_fewer_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(restore_mysql, "create_database", lambda url, database: None)
    monkeypatch.setattr(restore_mysql, "count_tables", lambda url, database: 7)

    with pytest.raises(RestoreError, match="Restauração incompleta"):
        restore_dump(
            _dump(tmp_path),
            "crm_restore_check",
            database_url=SOURCE,
            create=True,
            compare=True,
            mysql_cmd=_consumer(),
            count_fn=lambda: 3,
        )


def test_compare_passes_when_table_counts_match(tmp_path, monkeypatch):
    monkeypatch.setattr(restore_mysql, "create_database", lambda url, database: None)
    monkeypatch.setattr(restore_mysql, "count_tables", lambda url, database: 7)

    result = restore_dump(
        _dump(tmp_path),
        "crm_restore_check",
        database_url=SOURCE,
        create=True,
        compare=True,
        mysql_cmd=_consumer(),
        count_fn=lambda: 7,
    )

    assert result.tables == 7
    assert result.source_tables == 7
