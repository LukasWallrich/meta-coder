"""App-level settings (todo.md step 19) — global, not per-project: request
timeout/reasoning effort/service tier are per-project (settings.py, since a
project's own extraction workload is what they tune); upload size cap applies
to every project uniformly, so it lives here instead, persisted under
`app_data_dir()` alongside the projects themselves.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import app_data_dir


MIN_UPLOAD_SIZE_CAP_MB = 1
MAX_UPLOAD_SIZE_CAP_MB = 1024
DEFAULT_UPLOAD_SIZE_CAP_MB = 128


@dataclass
class AppSettings:
    upload_size_cap_mb: int = DEFAULT_UPLOAD_SIZE_CAP_MB

    def clamped(self) -> "AppSettings":
        return AppSettings(
            upload_size_cap_mb=max(
                MIN_UPLOAD_SIZE_CAP_MB, min(int(self.upload_size_cap_mb), MAX_UPLOAD_SIZE_CAP_MB)
            )
        )

    @property
    def upload_size_cap_bytes(self) -> int:
        return self.upload_size_cap_mb * 1024 * 1024


def _settings_path() -> Path:
    return app_data_dir() / "app_settings.json"


def load_app_settings() -> AppSettings:
    path = _settings_path()
    if not path.is_file():
        return AppSettings().clamped()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return AppSettings().clamped()
        return AppSettings(
            upload_size_cap_mb=int(raw.get("upload_size_cap_mb") or DEFAULT_UPLOAD_SIZE_CAP_MB)
        ).clamped()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings().clamped()


def save_app_settings(settings: AppSettings) -> AppSettings:
    normalized = settings.clamped()
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(normalized), indent=2) + "\n", encoding="utf-8")
    return normalized
