"""Per-project run settings — model, parallelism, request pacing (plan.md Part
A6: "different models have very different sane concurrency/pacing defaults").

The API key is deliberately NOT here: it's a single global, session-only value
(see web.py's Runtime.session_api_key / the global Settings page), not
per-project — one key is used across every project in a running session.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .gemini import DEFAULT_MODEL
from .projects import Project


MAX_PARALLEL_REQUESTS = 32
MAX_REQUEST_DELAY_SEC = 3600


@dataclass
class RunSettings:
    model: str = DEFAULT_MODEL
    parallel_requests: int = 1
    request_delay_sec: int = 0

    def clamped(self) -> "RunSettings":
        return RunSettings(
            model=(self.model or "").strip() or DEFAULT_MODEL,
            parallel_requests=max(1, min(int(self.parallel_requests), MAX_PARALLEL_REQUESTS)),
            request_delay_sec=max(0, min(int(self.request_delay_sec), MAX_REQUEST_DELAY_SEC)),
        )


def _settings_path(project: Project) -> Path:
    return project.path / ".meta_coder" / "run_settings.json"


def load_run_settings(project: Project) -> RunSettings:
    path = _settings_path(project)
    if not path.is_file():
        return RunSettings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return RunSettings()
        return RunSettings(
            model=str(raw.get("model") or DEFAULT_MODEL),
            parallel_requests=int(raw.get("parallel_requests") or 1),
            request_delay_sec=int(raw.get("request_delay_sec") or 0),
        ).clamped()
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return RunSettings()


def save_run_settings(project: Project, settings: RunSettings) -> RunSettings:
    normalized = settings.clamped()
    path = _settings_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(normalized), indent=2) + "\n", encoding="utf-8")
    return normalized
