import json
import io
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from meta_coder import updates
from meta_coder.web import create_app


@pytest.mark.parametrize('payload,expected', [
    ({'tag_name': 'v0.2.0'}, '0.2.0'),
    ({'tag_name': '0.10.0'}, '0.10.0'),
    ({'tag_name': 'v0.1.0'}, None),
    ({'tag_name': 'v0.0.9'}, None),
    ({'tag_name': 'v2.0.0-rc1'}, None),
    ({'tag_name': 'v2.0.0', 'draft': True}, None),
    ({'tag_name': 'v2.0.0', 'prerelease': True}, None),
    ({'tag_name': '<script>'}, None),
    ({'tag_name': 123}, None),
    ({}, None), ([], None),
])
def test_release_comparison_and_cache(monkeypatch, payload, expected):
    monkeypatch.setattr(updates, '__version__', '0.1.0')
    fetch = Mock(return_value=io.StringIO(json.dumps(payload)))
    monkeypatch.setattr(updates, 'urlopen', fetch)
    checker = updates.UpdateChecker()
    assert checker.check() == expected
    assert checker.check() == expected
    fetch.assert_called_once()
    assert fetch.call_args.kwargs['timeout'] == 5
    assert fetch.call_args.args[0].full_url == 'https://api.github.com/repos/shaheedazaad/meta-coder/releases/latest'


@pytest.mark.parametrize('error', [OSError('offline'), TimeoutError(), ValueError('bad JSON'), TypeError()])
def test_failures_are_silent_and_cached(monkeypatch, error):
    fetch = Mock(side_effect=error)
    monkeypatch.setattr(updates, 'urlopen', fetch)
    checker = updates.UpdateChecker()
    assert checker.check() is None
    assert checker.check() is None
    assert fetch.call_count == 1


def test_cache_expires(monkeypatch):
    monkeypatch.setattr(updates, '__version__', '0.1.0')
    clock = Mock(return_value=0)
    monkeypatch.setattr(updates.time, 'monotonic', clock)
    fetch = Mock(side_effect=[io.StringIO(json.dumps({'tag_name': tag})) for tag in ('v1.0.0', 'v2.0.0')])
    monkeypatch.setattr(updates, 'urlopen', fetch)
    checker = updates.UpdateChecker()
    assert checker.check() == '1.0.0'
    clock.return_value = 21600
    assert checker.check() == '2.0.0'
    assert fetch.call_count == 2


def test_update_route_is_token_protected_and_banner_is_global(tmp_path, monkeypatch):
    monkeypatch.setenv('META_CODER_HOME', str(tmp_path))
    monkeypatch.setattr(updates.UpdateChecker, 'check', lambda self: '1.2.3')
    client = TestClient(create_app(token='secret', projects_root=tmp_path / 'projects'), base_url='http://localhost')
    assert client.get('/updates').status_code == 404
    assert client.get('/wrong/updates').status_code == 404
    assert client.get('/secret/updates').json() == {'version': '1.2.3'}
    for page in ('/secret/', '/secret/settings'):
        response = client.get(page)
        assert response.status_code == 200
        assert 'id="update-notice"' in response.text
        assert '/secret/updates' in response.text
        assert '/secret/static/updates.js' in response.text
