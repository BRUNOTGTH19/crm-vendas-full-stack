"""A13: segredos em repouso e a chave privada VAPID cifrada no banco."""
import pytest

from config import settings
from database import SessionLocal
from models.app_setting import AppSetting
from services import secret_box
from services.vapid_service import generate_vapid_keypair, get_vapid_keys

PUBLIC_NAME = "vapid_public_key"
PRIVATE_NAME = "vapid_private_key"


def test_encrypt_round_trip_and_format():
    encrypted = secret_box.encrypt("segredo-vapid")

    assert encrypted.startswith(secret_box.PREFIX)
    assert "segredo-vapid" not in encrypted
    assert secret_box.decrypt(encrypted) == "segredo-vapid"


def test_encryption_uses_a_fresh_nonce():
    first = secret_box.encrypt("mesmo-valor")
    second = secret_box.encrypt("mesmo-valor")

    assert first != second
    assert secret_box.decrypt(first) == secret_box.decrypt(second) == "mesmo-valor"


def test_legacy_plaintext_is_returned_untouched():
    assert secret_box.is_encrypted("texto-puro") is False
    assert secret_box.decrypt("texto-puro") == "texto-puro"


def test_tampered_payload_is_rejected():
    encrypted = secret_box.encrypt("segredo")
    tampered = encrypted[:-4] + ("AAAA" if not encrypted.endswith("AAAA") else "BBBB")

    with pytest.raises(secret_box.SecretBoxError):
        secret_box.decrypt(tampered)


def test_other_key_cannot_decrypt(monkeypatch):
    encrypted = secret_box.encrypt("segredo")

    monkeypatch.setattr(settings, "jwt_secret_key", "outra-chave-completamente-diferente")

    with pytest.raises(secret_box.SecretBoxError):
        secret_box.decrypt(encrypted)


def _clear_vapid_settings(db):
    db.query(AppSetting).filter(
        AppSetting.key.in_([PUBLIC_NAME, PRIVATE_NAME])
    ).delete(synchronize_session=False)
    db.commit()


def _disable_env_keys(monkeypatch):
    monkeypatch.setattr(settings, "vapid_public_key", "")
    monkeypatch.setattr(settings, "vapid_private_key", "")


def test_generated_private_key_is_persisted_encrypted(monkeypatch):
    _disable_env_keys(monkeypatch)
    with SessionLocal() as db:
        _clear_vapid_settings(db)
        public_key, private_key = get_vapid_keys(db)
        stored = db.query(AppSetting).filter(AppSetting.key == PRIVATE_NAME).one().value

        assert secret_box.is_encrypted(stored)
        assert secret_box.decrypt(stored) == private_key
        # A pública continua em texto claro (vai para o navegador).
        assert (
            db.query(AppSetting).filter(AppSetting.key == PUBLIC_NAME).one().value
            == public_key
        )

        # Estável entre chamadas: as subscrições existentes continuam válidas.
        assert get_vapid_keys(db) == (public_key, private_key)


def test_legacy_plaintext_private_key_is_migrated(monkeypatch):
    _disable_env_keys(monkeypatch)
    public_key, private_key = generate_vapid_keypair()
    with SessionLocal() as db:
        _clear_vapid_settings(db)
        db.add(AppSetting(key=PUBLIC_NAME, value=public_key))
        db.add(AppSetting(key=PRIVATE_NAME, value=private_key))
        db.commit()

        assert get_vapid_keys(db) == (public_key, private_key)

        stored = db.query(AppSetting).filter(AppSetting.key == PRIVATE_NAME).one().value
        assert secret_box.is_encrypted(stored)
        assert stored != private_key
