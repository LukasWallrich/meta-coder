"""Recover corrupt settings without consulting real user preferences."""
import pytest

from meta_coder import app_settings, settings
from meta_coder.projects import create_project


@pytest.mark.parametrize('content', ['[]', '42', 'null', '{broken', '{"upload_size_cap_mb": "bad", "parallel_requests": "bad"}'])
def test_corrupt_settings_fall_back_to_defaults(tmp_path, monkeypatch, content):
    global_path = tmp_path / 'app.json'
    global_path.write_text(content)
    monkeypatch.setattr(app_settings, '_settings_path', lambda: global_path)
    assert app_settings.load_app_settings() == app_settings.AppSettings().clamped()
    project = create_project('test', root=tmp_path / 'projects')
    local_path = project.path / '.meta_coder' / 'run_settings.json'
    local_path.write_text(content)
    assert settings.load_run_settings(project) == settings.RunSettings().clamped()
