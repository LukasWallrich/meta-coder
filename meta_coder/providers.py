"""Provider dispatch: the one place that knows both `gemini.py` and
`openrouter.py` exist. Everything else (runner.py, web.py) goes through this
module rather than importing either adapter directly, so adding a third
provider later only touches this file plus its own new adapter module.
"""

from __future__ import annotations

from pathlib import Path

from . import gemini, openrouter
from .coding_sheet import CodingSheetRow
from .extraction import ExtractionResult
from .manual import CodingManual


PROVIDERS = ("gemini", "openrouter")
DEFAULT_PROVIDER = "gemini"

DEFAULT_MODEL_BY_PROVIDER = {
    "gemini": gemini.DEFAULT_MODEL,
    "openrouter": openrouter.DEFAULT_MODEL,
}
DEFAULT_TIMEOUT_SEC_BY_PROVIDER = {
    "gemini": gemini.DEFAULT_TIMEOUT_SEC,
    "openrouter": openrouter.DEFAULT_TIMEOUT_SEC,
}
PROVIDER_LABELS = {"gemini": "Gemini", "openrouter": "OpenRouter"}


def default_model(provider: str) -> str:
    return DEFAULT_MODEL_BY_PROVIDER.get(provider, gemini.DEFAULT_MODEL)


def extract_pdf_effects(
    *,
    provider: str,
    pdf_path: Path,
    manual: CodingManual,
    rows: list[CodingSheetRow],
    api_key: str,
    model: str,
    timeout_sec: int | None = None,
    service_tier: str = gemini.DEFAULT_SERVICE_TIER,
    reasoning_effort: str = "",
) -> ExtractionResult:
    """Route to the right adapter. Each adapter keeps its own kwargs (Gemini's
    `service_tier`, OpenRouter's `reasoning_effort`) — this function picks out
    only the subset that provider actually accepts rather than forwarding both
    blindly, since neither adapter's signature accepts the other's kwarg."""

    if provider == "openrouter":
        return openrouter.extract_pdf_effects(
            pdf_path=pdf_path,
            manual=manual,
            rows=rows,
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec or openrouter.DEFAULT_TIMEOUT_SEC,
            reasoning_effort=reasoning_effort,
        )
    if provider == "gemini":
        return gemini.extract_pdf_effects(
            pdf_path=pdf_path,
            manual=manual,
            rows=rows,
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec or gemini.DEFAULT_TIMEOUT_SEC,
            service_tier=service_tier,
        )
    raise ValueError(f"Unknown provider: {provider!r} (use one of {PROVIDERS}).")
