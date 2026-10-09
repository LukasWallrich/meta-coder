import io
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request
import pytest
from meta_coder import gemini
from meta_coder.extraction import ExtractionCancelled


def error(status=503, retry_after=None):
    headers = {} if retry_after is None else {'Retry-After': retry_after}
    return HTTPError('https://example.test', status, 'temporary', headers, io.BytesIO(b'error'))


def test_retry_after_is_honored_and_exchange_is_retried(monkeypatch):
    event = Mock()
    event.is_set.return_value = False
    event.wait.return_value = False
    transport = Mock(side_effect=[error(429, '2'), b'ok'])
    monkeypatch.setattr(gemini, 'audited_transport', transport)
    assert gemini._gemini_transport(Request('https://example.test'), timeout_sec=9, cancel_event=event) == b'ok'
    event.wait.assert_called_once_with(2.)
    assert transport.call_count == 2


@pytest.mark.parametrize('status,attempts', [(400, 1), (401, 1), (503, 3)])
def test_retry_count_is_bounded_and_permanent_errors_are_not_retried(monkeypatch, status, attempts):
    event = Mock()
    event.is_set.return_value = False
    event.wait.return_value = False
    transport = Mock(side_effect=lambda *a, **k: (_ for _ in ()).throw(error(status)))
    monkeypatch.setattr(gemini, 'audited_transport', transport)
    with pytest.raises(HTTPError):
        gemini._gemini_transport(Request('https://example.test'), timeout_sec=9, cancel_event=event)
    assert transport.call_count == attempts


def test_cancel_during_backoff_stops_further_requests(monkeypatch):
    event = Mock()
    event.is_set.return_value = False
    event.wait.return_value = True
    transport = Mock(side_effect=error())
    monkeypatch.setattr(gemini, 'audited_transport', transport)
    with pytest.raises(ExtractionCancelled):
        gemini._gemini_transport(Request('https://example.test'), timeout_sec=9, cancel_event=event)
    assert transport.call_count == 1
