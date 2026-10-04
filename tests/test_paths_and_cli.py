"""Platform data locations and CLI delegation without starting a server."""
import runpy
from pathlib import Path

import pytest

from meta_coder import paths, web


@pytest.mark.parametrize(('platform', 'env', 'expected'), [
    ('win32', {'LOCALAPPDATA': '/local'}, '/local/Meta-Coder'),
    ('win32', {}, '/home/test/AppData/Local/Meta-Coder'),
    ('darwin', {}, '/home/test/Library/Application Support/Meta-Coder'),
    ('linux', {'XDG_DATA_HOME': ' /xdg '}, '/xdg/meta-coder'),
    ('linux', {}, '/home/test/.local/share/meta-coder'),
])
def test_platform_data_directory(monkeypatch, platform, env, expected):
    for key in ['META_CODER_HOME', 'LOCALAPPDATA', 'XDG_DATA_HOME']:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(paths.sys, 'platform', platform)
    monkeypatch.setattr(Path, 'home', lambda: Path('/home/test'))
    assert paths.app_data_dir() == Path(expected)
    assert paths.projects_dir() == Path(expected) / 'projects'


def test_explicit_home_is_expanded_and_resolved(monkeypatch, tmp_path):
    monkeypatch.setenv('META_CODER_HOME', ' ~/data ')
    monkeypatch.setenv('HOME', str(tmp_path))
    assert paths.app_data_dir() == tmp_path / 'data'


def test_cli_returns_server_exit_code(monkeypatch):
    monkeypatch.setattr(web, 'launch_web', lambda: 7)
    namespace = runpy.run_module('meta_coder.__main__', run_name='cli_test')
    assert namespace['main']() == 7
    with pytest.raises(SystemExit) as stopped:
        runpy.run_module('meta_coder.__main__', run_name='__main__')
    assert stopped.value.code == 7
