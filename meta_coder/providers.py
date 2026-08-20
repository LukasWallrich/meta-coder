"""Provider dispatch: the one place that knows both `gemini.py` and
`openrouter.py` exist. Everything else (runner.py, web.py) goes through this
module rather than importing either adapter directly, so adding a third
provider later only touches this file plus its own new adapter module.
"""

from __future__ import annotations

from pathlib import Path
import threading

from . import gemini, openrouter
from .coding_sheet import CodingSheetRow
from .extraction import ExtractionResult
from .manual import CodingManual
from .manual_drafting import (
    build_manual_draft_prompt,
    build_manual_draft_schema,
    parse_manual_draft_response,
)


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


def check_model(provider: str, model: str, *, api_key: str) -> list[str]:
    if provider == "gemini":
        return gemini.check_model(model, api_key=api_key)
    if provider == "openrouter":
        return openrouter.check_model(model, api_key=api_key)
    return [f"Unknown provider: {provider!r}."]


def draft_coding_manual(
    *,
    provider: str,
    document_text: str,
    api_key: str,
    model: str,
    timeout_sec: int | None = None,
    service_tier: str = gemini.DEFAULT_SERVICE_TIER,
    reasoning_effort: str = "",
) -> CodingManual:
    """Draft and validate a manual using the project's selected provider."""

    prompt = build_manual_draft_prompt(document_text)
    if provider == "openrouter":
        raw_text = openrouter.generate_structured_text(
            prompt=prompt,
            response_schema=build_manual_draft_schema(dialect="json_schema"),
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec or openrouter.DEFAULT_TIMEOUT_SEC,
            reasoning_effort=reasoning_effort,
        )
    elif provider == "gemini":
        raw_text = gemini.generate_structured_text(
            prompt=prompt,
            response_schema=build_manual_draft_schema(),
            api_key=api_key,
            model=model,
            timeout_sec=timeout_sec or gemini.DEFAULT_TIMEOUT_SEC,
            service_tier=service_tier,
        )
    else:
        raise ValueError(f"Unknown provider: {provider!r} (use one of {PROVIDERS}).")
    return parse_manual_draft_response(raw_text)


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
    cancel_event: threading.Event | None = None,
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
            cancel_event=cancel_event,
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
            cancel_event=cancel_event,
        )
    raise ValueError(f"Unknown provider: {provider!r} (use one of {PROVIDERS}).")
