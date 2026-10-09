"""Candidate freshness policy: verify the inputs behind a selected result."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json

from .manual import manual_to_yaml_text
from .prompts import PROMPT_VERSION


def input_fingerprint(project, manual, rows, *, provider, model, reasoning_effort='', base_url='', response_format='json_schema'):
    digest = hashlib.sha256()
    try:
        with (project.sources_dir / rows[0].source_pdf).open('rb') as source:
            while chunk := source.read(1024 * 1024):
                digest.update(chunk)
    except (OSError, IndexError):
        return None
    inputs = {
        'fingerprint_version': 1, 'prompt_version': PROMPT_VERSION,
        'manual': manual_to_yaml_text(manual), 'rows': [asdict(row) for row in rows],
        'pdf_sha256': digest.hexdigest(), 'provider': provider, 'model': model,
        'reasoning_effort': reasoning_effort if provider != 'gemini' else '',
        'base_url': base_url if provider == 'openai_compatible' else '',
        'response_format': response_format if provider == 'openai_compatible' else '',
    }
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def current_results(project, manual, sheet, results, **settings):
    verified = {}
    for name, result in results.items():
        fingerprint = input_fingerprint(project, manual, sheet.rows_for_pdf(name), **settings) if manual else None
        if fingerprint and result.input_fingerprint == fingerprint:
            verified[name] = result
        else:
            verified[name] = replace(result, status='stale', coded_by_row_id={},
                                     error='Inputs changed or legacy inputs cannot be verified. Re-run this PDF.')
    return verified
