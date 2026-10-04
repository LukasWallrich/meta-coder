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


@pytest.mark.parametrize("provider", ["gemini", "openrouter", "openai_compatible"])
def test_save_load_clear_round_trip(fake_backend, provider):
    assert credentials.load_key(provider) is None
    credentials.save_key(provider, "secret-123")
    assert credentials.load_key(provider) == "secret-123"
    credentials.clear_key(provider)
    assert credentials.load_key(provider) is None


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


def test_keyring_available_false_without_usable_backend(monkeypatch):
    monkeypatch.setattr(keyring, "get_keyring", lambda: type("Unavailable", (), {"priority": 0})())
    assert credentials.keyring_available() is False


def test_load_key_reports_when_backend_is_broken(broken_backend):
    with pytest.raises(credentials.CredentialStoreError, match="could not be opened"):
        credentials.load_key("gemini")


def test_save_marks_success_without_reading_keychain(fake_backend, monkeypatch):
    monkeypatch.setattr(keyring, "get_password", lambda *_args: pytest.fail("Save must not read Keychain"))
    credentials.save_key("gemini", "secret")
    assert credentials.saved_key_configured("gemini") is True
    assert fake_backend._store[(credentials._SERVICE_NAME, "gemini")] == "secret"


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


def test_availability_does_not_request_keychain_access(fake_backend, monkeypatch):
    def unexpected_access(*args):
        pytest.fail("Checking availability must not read, write, or delete Keychain items")
    monkeypatch.setattr(keyring, "set_password", unexpected_access)
    monkeypatch.setattr(keyring, "get_password", unexpected_access)
    monkeypatch.setattr(keyring, "delete_password", unexpected_access)
    assert credentials.keyring_available() is True


def test_successful_keychain_write_does_not_require_read_permission(fake_backend, monkeypatch):
    def read_requires_permission(*args):
        raise keyring.errors.KeyringError("User interaction is not allowed")
    monkeypatch.setattr(keyring, "get_password", read_requires_permission)
    runtime = Runtime()
    runtime.set_api_key("openai_compatible", "test-only-key")
    assert fake_backend._store[(credentials._SERVICE_NAME, "openai_compatible")] == "test-only-key"
    assert runtime.api_key("openai_compatible") == "test-only-key"
    assert runtime.has_saved_key("openai_compatible") is True
    assert credentials.saved_key_configured("openai_compatible") is True


def test_saved_key_survives_runtime_restart(fake_backend):
    first = Runtime()
    first.set_api_key("gemini", "test-only-key")
    restarted = Runtime()
    assert restarted.has_saved_key("gemini") is True
    assert restarted.api_key("gemini") is None
    assert restarted.unlock_key("gemini") is True
    assert restarted.api_key("gemini") == "test-only-key"


def test_key_remains_recoverable_when_saved_marker_is_missing(fake_backend, tmp_path):
    first = Runtime()
    first.set_api_key("gemini", "test-only-key")
    credentials._saved_keys_path().unlink()
    restarted = Runtime()
    assert restarted.unlock_key("gemini") is True
    assert restarted.has_saved_key("gemini") is True


def test_action_loads_all_saved_keys_and_reuses_them(fake_backend, monkeypatch):
    for provider in ('gemini', 'openrouter'):
        credentials.save_key(provider, provider + '-secret')
    runtime = Runtime()
    reads = []
    def read(service, provider):
        reads.append(provider)
        return fake_backend.get_password(service, provider)
    monkeypatch.setattr(keyring, 'get_password', read)
    assert runtime.provider_ready('gemini')
    assert runtime.has_any_api_key()
    assert reads == []
    assert runtime.prepare_provider('gemini', 'model') is None
    assert set(reads) == {'gemini', 'openrouter'}
    assert runtime.api_key('openrouter') == 'openrouter-secret'
    assert runtime.prepare_provider('gemini', 'model') is None
    assert len(reads) == 2


def test_denied_keychain_access_can_be_retried(fake_backend, monkeypatch):
    credentials.save_key('gemini', 'secret')
    runtime = Runtime()
    def denied(*args):
        raise keyring.errors.KeyringError('User denied access')
    monkeypatch.setattr(keyring, 'get_password', denied)
    assert 'could not be opened' in runtime.prepare_provider('gemini', 'model')
    assert runtime.api_key('gemini') is None
    assert runtime.has_saved_key('gemini')
    monkeypatch.setattr(keyring, 'get_password', fake_backend.get_password)
    assert runtime.prepare_provider('gemini', 'model') is None
    assert runtime.api_key('gemini') == 'secret'


def test_action_reports_a_deleted_saved_key(fake_backend):
    credentials.mark_saved_key_configured('gemini', True)
    runtime = Runtime()
    assert 'no longer' in runtime.prepare_provider('gemini', 'model')
    assert not runtime.provider_ready('gemini')


def test_backend_initialization_failure_is_unavailable(monkeypatch):
    def fail():
        raise RuntimeError('backend setup failed')
    monkeypatch.setattr(keyring, 'get_keyring', fail)
    assert not credentials.keyring_available()


def test_unwritable_flags_do_not_prevent_secure_key_storage(fake_backend, monkeypatch, tmp_path):
    blocked = tmp_path / 'file'
    blocked.write_text('not a directory')
    monkeypatch.setattr(credentials, '_saved_keys_path', lambda: blocked / 'flags.json')
    assert not credentials.mark_saved_key_configured('gemini', True)
    credentials.save_key('gemini', ' secret ')
    assert credentials.load_key('gemini') == 'secret'
    credentials.clear_key('gemini')
    assert credentials.load_key('gemini') is None


def test_empty_key_is_rejected_without_backend_access(fake_backend):
    with pytest.raises(ValueError, match='empty'):
        credentials.save_key('gemini', '  ')
    assert fake_backend._store == {}


def test_missing_backend_rejects_save(monkeypatch):
    monkeypatch.setattr(credentials, 'keyring_available', lambda: False)
    with pytest.raises(credentials.CredentialStoreError, match='No operating-system'):
        credentials.save_key('gemini', 'secret')


def test_backend_save_error_is_wrapped(broken_backend):
    with pytest.raises(credentials.CredentialStoreError, match='could not save'):
        credentials.save_key('gemini', 'secret')


def test_unknown_provider_clear_never_touches_backend(monkeypatch):
    monkeypatch.setattr(keyring, 'delete_password', lambda *a: pytest.fail('unexpected credential access'))
    credentials.clear_key('unknown')


def test_clear_failure_keeps_saved_marker(fake_backend, monkeypatch):
    credentials.save_key('gemini', 'secret')
    def fail(*args):
        raise RuntimeError('store locked')
    monkeypatch.setattr(keyring, 'delete_password', fail)
    with pytest.raises(credentials.CredentialStoreError, match='could not remove'):
        credentials.clear_key('gemini')
    assert credentials.saved_key_configured('gemini')
    assert credentials.load_key('gemini') == 'secret'
