"""API key storage (todo.md step 9): session-only by default (matches the app's
original behavior — never touches disk), with an explicit opt-in per key to also
save it to the OS credential store (macOS Keychain / Windows Credential Locker /
Linux Secret Service via python-keyring) so it's there again next launch.

Deliberately never falls back to writing a plaintext file if the OS store is
unavailable — `keyring_available()` tells the caller so the UI can say so, and
the key just stays session-only instead.
"""

from __future__ import annotations

import keyring
import keyring.errors

from .paths import APP_NAME
from .providers import PROVIDERS


_SERVICE_NAME = f"{APP_NAME} API key"


def _username(provider: str) -> str:
    return provider


def keyring_available() -> bool:
    """Best-effort probe: a real round-trip (set + get + delete a throwaway
    entry), since `keyring.get_keyring()` can return a backend object that
    exists but doesn't actually work in this environment (e.g. no Secret
    Service daemon running on a headless Linux box)."""

    probe_user = "__meta_coder_probe__"
    try:
        keyring.set_password(_SERVICE_NAME, probe_user, "x")
        keyring.delete_password(_SERVICE_NAME, probe_user)
        return True
    except keyring.errors.KeyringError:
        return False
    except Exception:  # noqa: BLE001 - a broken backend can raise almost anything
        return False


def save_key(provider: str, api_key: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider!r}")
    keyring.set_password(_SERVICE_NAME, _username(provider), api_key)


def load_key(provider: str) -> str | None:
    if provider not in PROVIDERS:
        return None
    try:
        return keyring.get_password(_SERVICE_NAME, _username(provider))
    except keyring.errors.KeyringError:
        return None


def clear_key(provider: str) -> None:
    if provider not in PROVIDERS:
        return
    try:
        keyring.delete_password(_SERVICE_NAME, _username(provider))
    except keyring.errors.PasswordDeleteError:
        pass  # nothing was stored — clearing an already-clear key is not an error
