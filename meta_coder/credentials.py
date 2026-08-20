"""Secure API-key persistence in the operating system credential store.

Every key accepted by MetaCoder is saved through python-keyring (macOS Keychain /
Windows Credential Locker / Linux Secret Service) and verified with an immediate
read-back. There is deliberately no session-only or plaintext-file fallback: if
secure persistence is unavailable, adding the key fails visibly.
"""

from __future__ import annotations

import keyring
import keyring.errors
import json
from pathlib import Path

from .paths import app_data_dir
from .paths import APP_NAME
from .providers import PROVIDERS


_SERVICE_NAME = f"{APP_NAME} API key"


class CredentialStoreError(RuntimeError):
    """The operating-system credential store could not complete an operation."""


def _saved_keys_path() -> Path:
    return app_data_dir() / "saved_api_keys.json"


def _username(provider: str) -> str:
    return provider


def keyring_available() -> bool:
    """Best-effort probe: a real round-trip (set + get + delete a throwaway
    entry), since `keyring.get_keyring()` can return a backend object that
    exists but doesn't actually work in this environment (e.g. no Secret
    Service daemon running on a headless Linux box)."""

    probe_user = "__meta_coder_probe__"
    probe_value = "meta-coder-keyring-probe"
    try:
        keyring.set_password(_SERVICE_NAME, probe_user, probe_value)
        retrieved = keyring.get_password(_SERVICE_NAME, probe_user)
        keyring.delete_password(_SERVICE_NAME, probe_user)
        return retrieved == probe_value
    except keyring.errors.KeyringError:
        return False
    except Exception:  # noqa: BLE001 - a broken backend can raise almost anything
        return False


def _saved_key_flags() -> dict[str, bool]:
    path = _saved_keys_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def saved_key_configured(provider: str) -> bool:
    """Return saved-key state without opening or reading the keychain."""

    return _saved_key_flags().get(provider) is True


def mark_saved_key_configured(provider: str, configured: bool) -> bool:
    """Record saved-key state for the UI without making keychain use depend on it."""

    flags = _saved_key_flags()
    if configured:
        flags[provider] = True
    else:
        flags.pop(provider, None)
    path = _saved_keys_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(flags, indent=2) + "\n", encoding="utf-8")
        return True
    except OSError:
        # The keychain remains authoritative; an unavailable preferences path
        # must not prevent a user from saving or later unlocking their key.
        return False


def save_key(provider: str, api_key: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")
    try:
        keyring.set_password(_SERVICE_NAME, _username(provider), api_key)
        saved = keyring.get_password(_SERVICE_NAME, _username(provider))
    except Exception as exc:
        raise CredentialStoreError(
            "The OS credential store could not save the key. Check that Keychain or your "
            "system credential service is available, then try again."
        ) from exc
    if saved != api_key:
        raise CredentialStoreError(
            "The OS credential store did not return the key after saving it. The key was not accepted."
        )
    mark_saved_key_configured(provider, True)


def load_key(provider: str) -> str | None:
    if provider not in PROVIDERS:
        return None
    try:
        return keyring.get_password(_SERVICE_NAME, _username(provider))
    except Exception as exc:
        raise CredentialStoreError(
            "The OS credential store could not be opened. Check that Keychain or your "
            "system credential service is available, then try again."
        ) from exc


def clear_key(provider: str) -> None:
    if provider not in PROVIDERS:
        return
    try:
        keyring.delete_password(_SERVICE_NAME, _username(provider))
    except keyring.errors.PasswordDeleteError:
        pass  # nothing was stored — clearing an already-clear key is not an error
    except Exception as exc:
        raise CredentialStoreError("The OS credential store could not remove the key.") from exc
    mark_saved_key_configured(provider, False)
