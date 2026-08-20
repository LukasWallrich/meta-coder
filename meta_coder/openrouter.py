"""OpenRouter provider adapter (plan.md Part A4, todo.md step 17) — a backup path
to Gemini's, routing through whatever underlying model the user names.

Uses the OpenAI-compatible chat completions shape OpenRouter exposes: PDFs go in
as a `file` content part (base64 data URL), and structured output is requested via
`response_format: {type: "json_schema", ...}` — see `mechanism.build_response_schema`
called with `dialect="json_schema"`. Deliberately does NOT set `strict: true`: our
manuals allow optional effect fields (not every property required), which OpenAI's
strict json_schema mode forbids without modeling every optional field as nullable
instead of absent — simpler and more faithful to just not claim strict conformance.

Unlike Gemini's adapter, this one retries transient failures (connection errors,
429, 5xx) with bounded exponential backoff — OpenRouter fans a single request out
to one of several possible backend providers per model, so a transient failure at
one of them is more common here than hitting Gemini's API directly.
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .coding_sheet import CodingSheetRow
from .extraction import ExtractionResult, ProviderError
from .manual import CodingManual
from .mechanism import ValidationResult, build_response_schema, validate_response


API_BASE = "https://openrouter.ai/api/v1"
# A long-standing, stable OpenRouter model slug that supports both file input and
# structured outputs — a reasonable starting point, not a recommendation to stay
# on. The model field is free text (todo.md: "manual model-ID entry"); use
# `list_models`/`check_model` to verify whatever you actually pick.
DEFAULT_MODEL = "openai/gpt-4o-mini"
DEFAULT_TIMEOUT_SEC = 600
MAX_RETRIES = 3
RETRY_BACKOFF_BASE_SEC = 2.0
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504}

BASELINE_RULES = """You are a research assistant coding effects for a meta-analysis.

Rules:
1. Only use information present in the article. No outside knowledge, no inference
   or best-guessing, unless a field's description explicitly says otherwise.
2. If the article does not report a value for a field, set "value" to "Not Reported"
   and say so in "evidence" rather than guessing.
3. Code values must follow the exact formatting the field description specifies
   (units, decimal places, category label text).
4. "evidence" must be concise but specific: include a page number and/or a short
   quotation, not a vague paraphrase.
5. For a categorical field, report exactly one level unless its description states
   that multiple levels are valid.
6. Every object in "effects" MUST include a "row_id" that exactly matches one of the
   requested row IDs below. Never invent, rename, or omit a row_id. Return exactly
   one object per requested row, no more, no fewer."""


def _build_prompt(manual: CodingManual, rows: list[CodingSheetRow]) -> str:
    row_lines = "\n".join(f"- row_id: {row.row_id}\n  locator: {row.locator}" for row in rows)
    return (
        f"{BASELINE_RULES}\n\n"
        f"Effect definition for this meta-analysis:\n{manual.effect_definition}\n\n"
        f"Code the following {len(rows)} row(s) from the attached PDF. Each row is one "
        "study/experiment/condition; use its locator to find the right one:\n"
        f"{row_lines}"
    )


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "[redacted]") if api_key else text


def _request(url: str, *, api_key: str, body: dict[str, Any] | None = None, method: str = "GET"):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    return urllib.request.Request(url, data=data, headers=headers, method=method)


def list_models(*, api_key: str = "", timeout_sec: int = 20) -> list[dict[str, Any]]:
    """GET /models — public, doesn't require a key, but one is sent if given (it's
    harmless and matches how every other request to this API is made)."""

    request = _request(f"{API_BASE}/models", api_key=api_key)
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach OpenRouter: {exc}") from exc
    return body.get("data") or []


def check_model(model: str, *, api_key: str = "", timeout_sec: int = 20) -> list[str]:
    """Live validation (todo.md step 17): fetch OpenRouter's model list and report
    anything about `model` that would undermine this app's mechanism — never
    raises for a network hiccup, since that shouldn't block using a model you
    already know works; it just can't confirm anything this time."""

    try:
        models = list_models(api_key=api_key, timeout_sec=timeout_sec)
    except ProviderError as exc:
        return [f"Could not check this model right now: {exc}"]

    entry = next((m for m in models if m.get("id") == model), None)
    if entry is None:
        return [f"`{model}` was not found in OpenRouter's current model list — check the exact slug."]

    problems = []
    supported = set(entry.get("supported_parameters") or [])
    if "structured_outputs" not in supported:
        problems.append(
            "This model isn't listed as supporting structured outputs — coded values may "
            "come back malformed or fail to parse, since this app relies on schema-constrained "
            "JSON, not prompt-only formatting instructions."
        )
    modalities = set((entry.get("architecture") or {}).get("input_modalities") or [])
    if "file" not in modalities:
        problems.append(
            "This model has no native file/PDF input — OpenRouter will OCR-convert the PDF "
            "to text first (extra cost, and any information conveyed only visually — figures, "
            "tables with unusual layouts — may be lost)."
        )
    return problems


def _call_openrouter(
    *,
    model: str,
    api_key: str,
    prompt: str,
    pdf_bytes: bytes,
    filename: str,
    response_schema: dict[str, Any],
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    reasoning_effort: str = "",
) -> tuple[str, dict[str, int | None]]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {
                            "filename": filename,
                            "file_data": "data:application/pdf;base64,"
                            + base64.b64encode(pdf_bytes).decode("ascii"),
                        },
                    },
                ],
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "meta_coder_effects", "schema": response_schema},
        },
        "temperature": 0,
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}

    last_error: ProviderError | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        request = _request(
            f"{API_BASE}/chat/completions", api_key=api_key, body=payload, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_sec) as response:
                body = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            detail = _redact(exc.read().decode("utf-8", errors="replace"), api_key)
            last_error = ProviderError(f"OpenRouter API error ({exc.code}): {detail}")
            if exc.code not in RETRYABLE_STATUS or attempt == MAX_RETRIES:
                raise last_error from exc
        except urllib.error.URLError as exc:
            last_error = ProviderError(f"Could not reach OpenRouter: {_redact(str(exc.reason), api_key)}")
            if attempt == MAX_RETRIES:
                raise last_error from exc
        time.sleep(RETRY_BACKOFF_BASE_SEC * (2 ** (attempt - 1)))
    else:  # pragma: no cover - loop always breaks or raises above
        raise last_error or ProviderError("OpenRouter request failed for an unknown reason.")

    choices = body.get("choices") or []
    if not choices:
        raise ProviderError("OpenRouter returned no choices.", raw_response=json.dumps(body))
    message = choices[0].get("message") or {}
    text = message.get("content")
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("OpenRouter returned no message content.", raw_response=json.dumps(body))

    usage = body.get("usage") or {}
    tokens = {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }
    return text, tokens


def extract_pdf_effects(
    *,
    pdf_path: Path,
    manual: CodingManual,
    rows: list[CodingSheetRow],
    api_key: str,
    model: str = DEFAULT_MODEL,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    reasoning_effort: str = "",
) -> ExtractionResult:
    source_pdf = pdf_path.name
    requested_ids = {row.row_id for row in rows}
    started = time.monotonic()
    response_schema = build_response_schema(manual, dialect="json_schema")
    prompt = _build_prompt(manual, rows)

    try:
        raw_text, tokens = _call_openrouter(
            model=model,
            api_key=api_key,
            prompt=prompt,
            pdf_bytes=pdf_path.read_bytes(),
            filename=source_pdf,
            response_schema=response_schema,
            timeout_sec=timeout_sec,
            reasoning_effort=reasoning_effort,
        )
    except ProviderError as exc:
        return ExtractionResult(
            source_pdf=source_pdf,
            status="error",
            error=str(exc),
            raw_response=exc.raw_response,
            duration_sec=time.monotonic() - started,
        )

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return ExtractionResult(
            source_pdf=source_pdf,
            status="error",
            error=f"OpenRouter returned invalid JSON: {exc}",
            raw_response=raw_text,
            duration_sec=time.monotonic() - started,
        )

    result: ValidationResult = validate_response(parsed, requested_ids)
    duration = time.monotonic() - started
    if not result.ok:
        return ExtractionResult(
            source_pdf=source_pdf,
            status="needs_review",
            coded_by_row_id=result.coded_by_row_id,
            missing_ids=result.missing_ids,
            extra_ids=result.extra_ids,
            error=result.error,
            raw_response=raw_text,
            duration_sec=duration,
            input_tokens=tokens.get("input_tokens"),
            output_tokens=tokens.get("output_tokens"),
        )

    return ExtractionResult(
        source_pdf=source_pdf,
        status="ok",
        coded_by_row_id=result.coded_by_row_id,
        raw_response=raw_text,
        duration_sec=duration,
        input_tokens=tokens.get("input_tokens"),
        output_tokens=tokens.get("output_tokens"),
    )
