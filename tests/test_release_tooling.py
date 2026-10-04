"""Exercise the real builder against a committed fixture, including offline help."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_release_bundle_uses_selected_commit_and_includes_docs(tmp_path):
    pytest.importorskip('mkdocs')
    for name in ('scripts', 'docs', 'meta_coder/static'):
        shutil.copytree(ROOT / name, tmp_path / name)
    for name in ('pyproject.toml', 'pixi.lock', 'mkdocs.yml'):
        shutil.copy2(ROOT / name, tmp_path / name)
    def git(*args):
        return subprocess.run(['git', *args], cwd=tmp_path, check=True, capture_output=True)
    git('init')
    git('add', '.')
    git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'Fixture')
    (tmp_path / 'scripts/install.sh').write_text('UNCOMMITTED CONTENT')
    subprocess.run(['bash', 'scripts/build_release.sh', 'HEAD'], cwd=tmp_path,
                   env={**os.environ, 'PYTHON': sys.executable}, check=True, capture_output=True)
    dist = tmp_path / 'dist'
    version = (dist / 'latest.txt').read_text().strip()
    with tarfile.open(dist / f'meta-coder-{version}.tar.gz') as archive:
        prefix = f'meta-coder-{version}/'
        assert prefix + 'meta_coder/documentation/index.html' in archive.getnames()
        assert prefix + 'meta_coder/documentation/assets/app.css' in archive.getnames()
        assert prefix + 'pixi.lock' in archive.getnames()
        assert b'UNCOMMITTED' not in archive.extractfile(prefix + 'scripts/install.sh').read()
    assert 'UNCOMMITTED' not in (dist / 'install.sh').read_text()
    for line in (dist / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ')
        assert hashlib.sha256((dist / name).read_bytes()).hexdigest() == digest


@pytest.mark.skipif(sys.platform == 'win32', reason='Unix installer')
@pytest.mark.parametrize('fail_install', [False, True])
def test_public_installer_downloads_pinned_bundle_and_preserves_data(tmp_path, fail_install):
    import io
    import json

    bundle = tmp_path / 'bundle.tar.gz'
    with tarfile.open(bundle, 'w:gz') as archive:
        body = b'[project]\nname = "fixture"\n'
        info = tarfile.TarInfo('meta-coder-1.2.3/pyproject.toml')
        info.size = len(body)
        archive.addfile(info, io.BytesIO(body))
    bin_dir = tmp_path / 'fake-bin'
    bin_dir.mkdir()
    log = tmp_path / 'downloads.jsonl'
    gh = bin_dir / 'curl'
    gh.write_text(f'''#!{sys.executable}
import json, pathlib, shutil, sys
args = sys.argv[1:]
with open({str(log)!r}, 'a') as f: f.write(json.dumps(args) + '\\n')
url = args[args.index('-fsSL') + 1]
out = args[args.index('-o') + 1]
if url.endswith('/latest.txt'): print('1.2.3')
else: shutil.copyfile({str(bundle)!r}, out)
''')
    gh.chmod(0o755)
    pixi = bin_dir / 'pixi'
    pixi.write_text('#!/bin/sh\nexit ' + ('1' if fail_install else '0') + '\n')
    pixi.chmod(0o755)
    home = tmp_path / 'home'
    home.mkdir()
    data = home / ('Library/Application Support/Meta-Coder' if sys.platform == 'darwin' else '.local/share/meta-coder')
    old = data / 'app/0.9.0'
    old.mkdir(parents=True)
    project = data / 'projects/keep.txt'
    project.parent.mkdir()
    project.write_text('keep me')
    env = {key: value for key, value in os.environ.items() if not key.startswith('META_CODER_') and key != 'XDG_DATA_HOME'}
    env.update(HOME=str(home), PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
    result = subprocess.run(['bash', str(ROOT / 'scripts/install.sh')], env=env, capture_output=True, text=True)
    assert result.returncode == (1 if fail_install else 0), result.stderr
    assert project.read_text() == 'keep me'
    assert old.exists() == fail_install
    downloads = [json.loads(line) for line in log.read_text().splitlines()]
    assert downloads[0][1] == 'https://github.com/shaheedazaad/meta-coder/releases/latest/download/latest.txt'
    assert downloads[1][1] == 'https://github.com/shaheedazaad/meta-coder/releases/download/v1.2.3/meta-coder-1.2.3.tar.gz'
    if not fail_install:
        launcher = (home / '.local/bin/meta-coder').read_text()
        assert str(pixi) in launcher
        assert '--locked' in launcher
