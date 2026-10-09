"""Regression checks for the review-only freshness and retry policy."""
import json
from dataclasses import replace
import pytest
from meta_coder.coding_sheet import CodingSheet, CodingSheetRow
from meta_coder.extraction import ExtractionResult
from meta_coder.fingerprints import current_results, input_fingerprint
from meta_coder.manual import parse_coding_manual
from meta_coder.projects import create_project
from meta_coder.runner import load_latest_attempts, load_persisted_results, raw_json_path, write_raw_result

@pytest.fixture
def context(tmp_path):
    project = create_project('Freshness', root=tmp_path)
    (project.sources_dir / 'paper.pdf').write_bytes(b'%PDF-original')
    manual = parse_coding_manual('effect_definition: comparison\neffects:\n  estimate: {type: number}\n')
    sheet = CodingSheet([CodingSheetRow('r1', 'paper.pdf', 'Table 1')], [])
    return project, manual, sheet


def fingerprint(context, **changes):
    project, manual, sheet = context
    return input_fingerprint(project, manual, sheet.rows, provider='gemini', model=changes.get('model', 'model'))


def test_unchanged_input_and_yaml_formatting_preserve_identity(context):
    project, manual, sheet = context
    first = fingerprint(context)
    manual.raw_text = '# formatting only'
    assert fingerprint(context) == first
    result = ExtractionResult('paper.pdf', 'ok', input_fingerprint=first)
    assert current_results(project, manual, sheet, {'paper.pdf': result}, provider='gemini', model='model')['paper.pdf'].status == 'ok'


@pytest.mark.parametrize('change', ['pdf', 'manual', 'locator', 'row_id', 'model', 'legacy'])
def test_changed_or_unverified_inputs_cannot_reuse_old_values(context, change):
    project, manual, sheet = context
    result = ExtractionResult('paper.pdf', 'ok', coded_by_row_id={'r1': {'estimate': {'value': 7}}}, input_fingerprint=fingerprint(context))
    if change == 'pdf': (project.sources_dir / 'paper.pdf').write_bytes(b'%PDF-replaced')
    if change == 'manual': manual.effects['estimate'].description = 'Different instructions'
    if change == 'locator': sheet.rows[0].locator = 'Table 2'
    if change == 'row_id': sheet.rows[0].row_id = 'r2'
    if change == 'legacy': result.input_fingerprint = None
    current = current_results(project, manual, sheet, {'paper.pdf': result}, provider='gemini', model='other' if change == 'model' else 'model')['paper.pdf']
    assert current.status == 'stale' and current.coded_by_row_id == {}
    assert result.coded_by_row_id


@pytest.mark.parametrize('status', ['error', 'cancelled', 'needs_review'])
def test_failed_retry_is_visible_without_erasing_verified_success(context, status):
    project, _, _ = context
    previous = ExtractionResult('paper.pdf', 'ok', raw_response='good', input_fingerprint=fingerprint(context))
    write_raw_result(project, previous, provider='gemini', model='model')
    attempt = ExtractionResult('paper.pdf', status, error='latest attempt failed', input_fingerprint=fingerprint(context))
    write_raw_result(project, attempt, provider='gemini', model='model')
    assert load_persisted_results(project)['paper.pdf'].raw_response == 'good'
    assert load_latest_attempts(project)['paper.pdf'].status == status


def test_success_for_other_inputs_is_never_selected_after_failed_retry(context):
    project, _, _ = context
    write_raw_result(project, ExtractionResult('paper.pdf', 'ok', input_fingerprint='old'), provider='gemini', model='model')
    write_raw_result(project, ExtractionResult('paper.pdf', 'error', input_fingerprint='new'), provider='gemini', model='model')
    assert load_persisted_results(project)['paper.pdf'].status == 'error'


def test_discarding_terminal_progress_prevents_stale_status():
    from meta_coder.runner import Runner, RunState
    runner = Runner()
    runner._states['project'] = RunState(status='complete', processed=4)
    runner.discard_completed_state('project')
    assert runner.state('project') is None
    runner._states['project'] = RunState(status='running')
    with pytest.raises(RuntimeError, match='active run'):
        runner.discard_completed_state('project')
    assert runner.is_running('project')
