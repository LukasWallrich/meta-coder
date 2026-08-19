"""Run execution: a worker pool sized to the project's configured
`parallel_requests`, plus a shared pacer enforcing a minimum interval between
request *starts* across all workers (plan.md Part A7) — "1 request every N
seconds" means that globally, not per worker. Defaults to parallel_requests=1,
request_delay_sec=0 (plain sequential, no artificial pacing) unless the user
configures otherwise on the project's Setup tab.
"""

from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .coding_sheet import CodingSheet
from .gemini import DEFAULT_MODEL, ExtractionResult, extract_pdf_effects
from .manual import CodingManual
from .projects import Project
from .results import collate_results, render_pdf_audit_yaml, rows_to_csv


_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_stem(source_pdf: str) -> str:
    return _SAFE_STEM_RE.sub("_", Path(source_pdf).stem)


def _raw_json_path(project: Project, source_pdf: str) -> Path:
    return project.raw_dir / f"{_safe_stem(source_pdf)}.json"


def audit_yaml_path(project: Project, source_pdf: str) -> Path:
    return project.audit_dir / f"{_safe_stem(source_pdf)}.yaml"


class _RequestPacer:
    """Enforces a minimum interval between request *starts*, shared across every
    worker thread — not a per-worker delay, a global one."""

    def __init__(self, delay_sec: int) -> None:
        self.delay_sec = max(0, int(delay_sec))
        self._last_started: float | None = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.delay_sec <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                remaining = 0.0 if self._last_started is None else self.delay_sec - (now - self._last_started)
                if remaining <= 0:
                    self._last_started = now
                    return
            time.sleep(min(remaining, 0.1))


@dataclass
class PdfProgress:
    source_pdf: str
    status: str = "pending"  # pending | running | ok | needs_review | error
    error: str | None = None
    missing_ids: list[str] = field(default_factory=list)
    extra_ids: list[str] = field(default_factory=list)


@dataclass
class RunState:
    status: str = "idle"  # idle | running | complete | failed
    total: int = 0
    processed: int = 0
    pdfs: list[PdfProgress] = field(default_factory=list)
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "total": self.total,
            "processed": self.processed,
            "error": self.error,
            "pdfs": [
                {
                    "source_pdf": p.source_pdf,
                    "status": p.status,
                    "error": p.error,
                    "missing_ids": p.missing_ids,
                    "extra_ids": p.extra_ids,
                }
                for p in self.pdfs
            ],
        }


class Runner:
    """Holds one RunState per project in memory. A single-user local app doesn't
    need persistence for run progress across restarts."""

    def __init__(self) -> None:
        self._states: dict[str, RunState] = {}
        self._lock = threading.Lock()

    def state(self, project_id: str) -> RunState | None:
        return self._states.get(project_id)

    def is_running(self, project_id: str) -> bool:
        state = self._states.get(project_id)
        return bool(state and state.status == "running")

    def start(
        self,
        *,
        project: Project,
        manual: CodingManual,
        coding_sheet: CodingSheet,
        api_key: str,
        model: str = DEFAULT_MODEL,
        parallel_requests: int = 1,
        request_delay_sec: int = 0,
    ) -> RunState:
        if self.is_running(project.project_id):
            raise RuntimeError("This project is already running.")

        pdf_names = sorted({row.source_pdf for row in coding_sheet.rows})
        state = RunState(
            status="running",
            total=len(pdf_names),
            pdfs=[PdfProgress(source_pdf=name) for name in pdf_names],
            started_at=time.time(),
        )
        with self._lock:
            self._states[project.project_id] = state

        thread = threading.Thread(
            target=self._run,
            args=(project, manual, coding_sheet, api_key, model, state, parallel_requests, request_delay_sec),
            daemon=True,
        )
        thread.start()
        return state

    def _run(
        self,
        project: Project,
        manual: CodingManual,
        coding_sheet: CodingSheet,
        api_key: str,
        model: str,
        state: RunState,
        parallel_requests: int,
        request_delay_sec: int,
    ) -> None:
        results_by_pdf: dict[str, ExtractionResult] = {}
        results_lock = threading.Lock()
        pacer = _RequestPacer(request_delay_sec)

        def process_one(progress: PdfProgress) -> None:
            progress.status = "running"
            pdf_path = project.sources_dir / progress.source_pdf
            rows = coding_sheet.rows_for_pdf(progress.source_pdf)
            pacer.wait()
            result = extract_pdf_effects(
                pdf_path=pdf_path,
                manual=manual,
                rows=rows,
                api_key=api_key,
                model=model,
            )
            _raw_json_path(project, progress.source_pdf).write_text(
                json.dumps(
                    {
                        "source_pdf": result.source_pdf,
                        "status": result.status,
                        "error": result.error,
                        "coded_by_row_id": result.coded_by_row_id,
                        "missing_ids": sorted(result.missing_ids),
                        "extra_ids": sorted(result.extra_ids),
                        "raw_response": result.raw_response,
                        "duration_sec": result.duration_sec,
                        "input_tokens": result.input_tokens,
                        "output_tokens": result.output_tokens,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            audit_yaml_path(project, progress.source_pdf).write_text(
                render_pdf_audit_yaml(
                    manual=manual, source_pdf=progress.source_pdf, rows=rows, result=result
                ),
                encoding="utf-8",
            )
            with results_lock:
                results_by_pdf[progress.source_pdf] = result
                progress.status = result.status
                progress.error = result.error
                progress.missing_ids = sorted(result.missing_ids)
                progress.extra_ids = sorted(result.extra_ids)
                state.processed += 1

        try:
            project.audit_dir.mkdir(parents=True, exist_ok=True)
            workers = max(1, min(int(parallel_requests), len(state.pdfs) or 1))
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = [executor.submit(process_one, progress) for progress in state.pdfs]
                for future in futures:
                    future.result()  # re-raises any worker exception here

            coded_rows, evidence_rows = collate_results(
                manual=manual, coding_sheet=coding_sheet, results_by_pdf=results_by_pdf
            )
            (project.output_dir / "coded_data.csv").write_text(
                rows_to_csv(coded_rows, manual), encoding="utf-8"
            )
            (project.output_dir / "evidence.csv").write_text(
                rows_to_csv(evidence_rows, manual), encoding="utf-8"
            )
            state.status = "complete"
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            state.status = "failed"
            state.error = str(exc)
        finally:
            state.finished_at = time.time()
