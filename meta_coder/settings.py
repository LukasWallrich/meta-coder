"""Per-project run settings — provider, model, parallelism, request pacing
(plan.md Part A6: "different models have very different sane concurrency/
pacing defaults").

The API key is deliberately NOT here: it's a global, per-provider, session-only
value by default (see web.py's Runtime / the global Settings page — optionally
persisted to the OS keyring, see credentials.py), not per-project — one key per
provider is used across every project in a running session.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .gemini import DEFAULT_SERVICE_TIER
from .projects import Project
from .providers import DEFAULT_PROVIDER, DEFAULT_TIMEOUT_SEC_BY_PROVIDER, PROVIDERS, default_model


MAX_PARALLEL_REQUESTS = 32
MAX_REQUEST_DELAY_SEC = 3600
MIN_REQUEST_TIMEOUT_SEC = 30
MAX_REQUEST_TIMEOUT_SEC = 3600
REASONING_EFFORTS = ("", "low", "medium", "high")


@dataclass
class RunSettings:
    provider: str = DEFAULT_PROVIDER
    model: str = ""
    parallel_requests: int = 1
    request_delay_sec: int = 0
    request_timeout_sec: int = 0  # 0 means "provider default" — see clamped()
    service_tier: str = DEFAULT_SERVICE_TIER  # Gemini only; ignored by other providers
    reasoning_effort: str = ""  # OpenRouter only; "" means "provider/model default"

    def clamped(self) -> "RunSettings":
        provider = self.provider if self.provider in PROVIDERS else DEFAULT_PROVIDER
        timeout_default = DEFAULT_TIMEOUT_SEC_BY_PROVIDER.get(provider, 600)
        timeout = int(self.request_timeout_sec or 0)
        return RunSettings(
            provider=provider,
            model=(self.model or "").strip() or default_model(provider),
            parallel_requests=max(1, min(int(self.parallel_requests), MAX_PARALLEL_REQUESTS)),
            request_delay_sec=max(0, min(int(self.request_delay_sec), MAX_REQUEST_DELAY_SEC)),
            request_timeout_sec=(
                timeout_default
                if timeout <= 0
                else max(MIN_REQUEST_TIMEOUT_SEC, min(timeout, MAX_REQUEST_TIMEOUT_SEC))
            ),
            service_tier=(self.service_tier or "").strip() or DEFAULT_SERVICE_TIER,
            reasoning_effort=(self.reasoning_effort or "").strip().lower()
            if (self.reasoning_effort or "").strip().lower() in REASONING_EFFORTS
            else "",
        )


def _settings_path(project: Project) -> Path:
    return project.path / ".meta_coder" / "run_settings.json"


def load_run_settings(project: Project) -> RunSettings:
    path = _settings_path(project)
    if not path.is_file():
        return RunSettings().clamped()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return RunSettings().clamped()
        return RunSettings(
            provider=str(raw.get("provider") or DEFAULT_PROVIDER),
            model=str(raw.get("model") or ""),
            parallel_requests=int(raw.get("parallel_requests") or 1),
            request_delay_sec=int(raw.get("request_delay_sec") or 0),
            request_timeout_sec=int(raw.get("request_timeout_sec") or 0),
            service_tier=str(raw.get("service_tier") or DEFAULT_SERVICE_TIER),
            reasoning_effort=str(raw.get("reasoning_effort") or ""),
        ).clamped()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return RunSettings().clamped()


def save_run_settings(project: Project, settings: RunSettings) -> RunSettings:
    normalized = settings.clamped()
    path = _settings_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(normalized), indent=2) + "\n", encoding="utf-8")
    return normalized
