"""Settings shared across every project.

Extraction settings remain per-project, while the upload cap and coding-manual
generator provider/model are global because they describe app-wide workflows.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .paths import app_data_dir
from .providers import DEFAULT_PROVIDER, PROVIDERS, default_model


MIN_UPLOAD_SIZE_CAP_MB = 1
MAX_UPLOAD_SIZE_CAP_MB = 1024
DEFAULT_UPLOAD_SIZE_CAP_MB = 128


@dataclass
class AppSettings:
    upload_size_cap_mb: int = DEFAULT_UPLOAD_SIZE_CAP_MB
    manual_generator_provider: str = DEFAULT_PROVIDER
    manual_generator_model: str = ""
    grobid_url: str = ""
    openai_base_url: str = ""
    openai_response_format: str = "json_schema"

    def clamped(self) -> "AppSettings":
        provider = (
            self.manual_generator_provider
            if self.manual_generator_provider in PROVIDERS
            else DEFAULT_PROVIDER
        )
        return AppSettings(
            upload_size_cap_mb=max(
                MIN_UPLOAD_SIZE_CAP_MB, min(int(self.upload_size_cap_mb), MAX_UPLOAD_SIZE_CAP_MB)
            ),
            manual_generator_provider=provider,
            manual_generator_model=(self.manual_generator_model or "").strip()
            or default_model(provider),
            grobid_url=(self.grobid_url or "").strip(),
            openai_base_url=(self.openai_base_url or "").strip().rstrip("/"),
            openai_response_format=self.openai_response_format
            if self.openai_response_format in {"json_schema", "json_object", "none"}
            else "json_schema",
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
            upload_size_cap_mb=int(raw.get("upload_size_cap_mb") or DEFAULT_UPLOAD_SIZE_CAP_MB),
            manual_generator_provider=str(
                raw.get("manual_generator_provider") or DEFAULT_PROVIDER
            ),
            manual_generator_model=str(raw.get("manual_generator_model") or ""),
            grobid_url=str(raw.get("grobid_url") or ""),
            openai_base_url=str(raw.get("openai_base_url") or ""),
            openai_response_format=str(raw.get("openai_response_format") or "json_schema"),
        ).clamped()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings().clamped()


def save_app_settings(settings: AppSettings) -> AppSettings:
    normalized = settings.clamped()
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(normalized), indent=2) + "\n", encoding="utf-8")
    return normalized


def endpoint_options(provider: str, settings: AppSettings | None = None) -> dict[str, str]:
    if provider != "openai_compatible":
        return {}
    settings = settings or load_app_settings()
    return {"base_url": settings.openai_base_url, "response_format": settings.openai_response_format}
