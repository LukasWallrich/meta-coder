"""Exercises credentials.py against fake keyring backends (never the real OS
credential store) so the test suite doesn't read/write the machine's actual
Keychain/Credential Locker/Secret Service on every run."""

import keyring
import keyring.errors
import pytest

from meta_coder import credentials
from meta_coder.web import Runtime


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
def isolated_saved_key_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(credentials, "_saved_keys_path", lambda: tmp_path / "saved_api_keys.json")


@pytest.fixture(autouse=True)
def _isolate_saved_key_flags(isolated_saved_key_flags):
    """Never let credential tests touch the developer's real saved-key marker."""


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


def test_existing_keychain_key_can_be_discovered_without_a_marker(fake_backend):
    fake_backend.set_password(credentials._SERVICE_NAME, "gemini", "existing-key")

    assert credentials.saved_key_configured("gemini") is False
    assert credentials.load_key("gemini") == "existing-key"
    assert credentials.mark_saved_key_configured("gemini", True) is True
    assert credentials.saved_key_configured("gemini") is True


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


def test_load_key_reports_when_backend_is_broken(broken_backend):
    with pytest.raises(credentials.CredentialStoreError, match="could not be opened"):
        credentials.load_key("gemini")


def test_save_requires_successful_read_back(fake_backend, monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda *_args: None)

    with pytest.raises(credentials.CredentialStoreError, match="did not return the key"):
        credentials.save_key("gemini", "secret")

    assert credentials.saved_key_configured("gemini") is False


def test_runtime_never_accepts_a_session_only_key(monkeypatch):
    runtime = Runtime()
    monkeypatch.setattr(
        credentials,
        "save_key",
        lambda *_args: (_ for _ in ()).throw(credentials.CredentialStoreError("save failed")),
    )

    with pytest.raises(credentials.CredentialStoreError, match="save failed"):
        runtime.set_api_key("gemini", "secret")

    assert runtime.api_key("gemini") is None
    assert runtime.has_saved_key("gemini") is False


def test_unlock_repairs_stale_saved_key_marker(fake_backend):
    credentials.mark_saved_key_configured("gemini", True)
    runtime = Runtime()
    assert runtime.has_saved_key("gemini") is True

    assert runtime.unlock_key("gemini") is False

    assert runtime.has_saved_key("gemini") is False
    assert credentials.saved_key_configured("gemini") is False
