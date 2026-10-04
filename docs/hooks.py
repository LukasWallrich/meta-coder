"""Bundle the app's actual styles and documentation images without duplicating sources."""
from pathlib import Path
from mkdocs.structure.files import File

ROOT = Path(__file__).resolve().parents[1]


def on_files(files, config):
    for name in ('app.css', 'vendor/basecoat.min.css', 'vendor/basecoat.LICENSE.txt'):
        item = File(name, str(ROOT / 'meta_coder/static'), config.site_dir, False)
        item.dest_uri = 'assets/' + name
        files.append(item)
    for source in sorted((ROOT / 'docs/assets').rglob('*')):
        if source.is_file():
            name = source.relative_to(ROOT / 'docs').as_posix()
            files.append(File(name, str(ROOT / 'docs'), config.site_dir, False))
    return files
