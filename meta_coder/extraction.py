"""Provider-agnostic result/error types shared by every LLM adapter (gemini.py,
openrouter.py). Kept separate from either adapter so neither module has to
import from the other, and so `runner.py`/`providers.py` can depend on one
stable shape regardless of which provider actually ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, raw_response: str | None = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


@dataclass
class ExtractionResult:
    source_pdf: str
    status: str  # "ok" | "needs_review" | "error"
    coded_by_row_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    missing_ids: set[str] = field(default_factory=set)
    extra_ids: set[str] = field(default_factory=set)
    raw_response: str | None = None
    error: str | None = None
    duration_sec: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
