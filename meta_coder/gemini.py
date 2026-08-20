"""Gemini provider adapter (plan.md Part A4 / Problem 2).

Sends the original PDF bytes natively, batches every coding-sheet row for one PDF
into a single request, and relies on `mechanism.validate_response` for the hard
row_id check. Uses the plain REST API via `urllib` rather than the SDK, to keep the
dependency footprint minimal and the request/response shape fully visible.
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


API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.7-flash"
DEFAULT_TIMEOUT_SEC = 600
DEFAULT_SERVICE_TIER = "flex"  # 50% lower cost, variable latency/best-effort availability

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


def _call_gemini(
    *,
    model: str,
    api_key: str,
    prompt: str,
    pdf_bytes: bytes,
    response_schema: dict[str, Any],
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    service_tier: str = DEFAULT_SERVICE_TIER,
) -> tuple[str, dict[str, int | None]]:
    url = f"{API_BASE}/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": "application/pdf",
                            "data": base64.b64encode(pdf_bytes).decode("ascii"),
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema,
            "temperature": 0,
        },
        # Flex tier: ~50% lower cost in exchange for variable latency and
        # best-effort availability (per Gemini API docs). Omit/"standard" for the
        # default tier.
        "service_tier": service_tier,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _redact(exc.read().decode("utf-8", errors="replace"), api_key)
        raise ProviderError(f"Gemini API error ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise ProviderError(f"Could not reach Gemini: {_redact(str(exc.reason), api_key)}") from exc

    candidates = body.get("candidates") or []
    parts = []
    for candidate in candidates:
        for part in ((candidate.get("content") or {}).get("parts") or []):
            if "text" in part:
                parts.append(part["text"])
    text = "".join(parts)
    if not text.strip():
        finish_reason = (candidates[0].get("finishReason") if candidates else None) or "unknown"
        raise ProviderError(f"Gemini returned no text (finishReason: {finish_reason}).")

    usage = body.get("usageMetadata") or {}
    tokens = {
        "input_tokens": usage.get("promptTokenCount"),
        "output_tokens": usage.get("candidatesTokenCount"),
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
    service_tier: str = DEFAULT_SERVICE_TIER,
) -> ExtractionResult:
    source_pdf = pdf_path.name
    requested_ids = {row.row_id for row in rows}
    started = time.monotonic()
    response_schema = build_response_schema(manual)
    prompt = _build_prompt(manual, rows)

    try:
        raw_text, tokens = _call_gemini(
            model=model,
            api_key=api_key,
            prompt=prompt,
            pdf_bytes=pdf_path.read_bytes(),
            response_schema=response_schema,
            timeout_sec=timeout_sec,
            service_tier=service_tier,
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
            error=f"Gemini returned invalid JSON: {exc}",
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
