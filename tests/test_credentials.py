"""Exercises credentials.py against fake keyring backends (never the real OS
credential store) so the test suite doesn't read/write the machine's actual
Keychain/Credential Locker/Secret Service on every run."""

import keyring
import keyring.errors
import pytest

from meta_coder import credentials


class _FakeBackend(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def __init__(self):
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        try:
            del self._store[(service, username)]
        except KeyError as exc:
            raise keyring.errors.PasswordDeleteError("not found") from exc


class _BrokenBackend(keyring.backend.KeyringBackend):
    priority = 1  # type: ignore[assignment]

    def set_password(self, service, username, password):
        raise keyring.errors.PasswordSetError("backend unavailable")

    def get_password(self, service, username):
        raise keyring.errors.KeyringError("backend unavailable")

    def delete_password(self, service, username):
        raise keyring.errors.PasswordDeleteError("backend unavailable")


@pytest.fixture
def fake_backend(monkeypatch):
    backend = _FakeBackend()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.setattr(keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keyring, "delete_password", backend.delete_password)
    return backend


@pytest.fixture
def broken_backend(monkeypatch):
    backend = _BrokenBackend()
    monkeypatch.setattr(keyring, "get_keyring", lambda: backend)
    monkeypatch.setattr(keyring, "set_password", backend.set_password)
    monkeypatch.setattr(keyring, "get_password", backend.get_password)
    monkeypatch.setattr(keyring, "delete_password", backend.delete_password)
    return backend


def test_save_load_clear_round_trip(fake_backend):
    assert credentials.load_key("gemini") is None
    credentials.save_key("gemini", "secret-123")
    assert credentials.load_key("gemini") == "secret-123"
    credentials.clear_key("gemini")
    assert credentials.load_key("gemini") is None


def test_providers_are_isolated(fake_backend):
    credentials.save_key("gemini", "gemini-key")
    credentials.save_key("openrouter", "openrouter-key")
    assert credentials.load_key("gemini") == "gemini-key"
    assert credentials.load_key("openrouter") == "openrouter-key"


def test_unknown_provider_rejected_on_save(fake_backend):
    with pytest.raises(ValueError):
        credentials.save_key("bogus", "x")
    assert credentials.load_key("bogus") is None


def test_clearing_an_already_clear_key_does_not_raise(fake_backend):
    credentials.clear_key("gemini")  # never saved — must not raise


def test_keyring_available_true_with_working_backend(fake_backend):
    assert credentials.keyring_available() is True


def test_keyring_available_false_with_broken_backend(broken_backend):
    assert credentials.keyring_available() is False


def test_load_key_returns_none_when_backend_broken(broken_backend):
    assert credentials.load_key("gemini") is None
