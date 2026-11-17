import datetime
import json
import shutil
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SCHEMAS = REPO / "schemas"
DESTINATION = HERE / "src" / "_schemas"


def _git(*args):
    if not (REPO / ".git").exists():
        return None
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def sync_schemas():
    sources = sorted(SCHEMAS.glob("*/*.schema.json"))
    if not sources:
        if any(DESTINATION.rglob("*.schema.json")):
            return  # build a partir de um sdist: a cópia já veio nele
        raise SystemExit(
            "setup.py: nenhum *.schema.json em ../schemas nem em src/_schemas. "
            "Rode o build de dentro do clone do repositório b1."
        )
    names = [source.name for source in sources]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise SystemExit(f"setup.py: nomes de schema repetidos em pastas diferentes: {duplicates}")
    shutil.rmtree(DESTINATION, ignore_errors=True)
    DESTINATION.mkdir(parents=True)
    (DESTINATION / "__init__.py").write_text("")
    for source in sources:
        shutil.copy2(source, DESTINATION / source.name)
    meta = {
        "commit": _git("rev-parse", "HEAD"),
        "description": _git("describe", "--tags", "--always", "--dirty"),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
    }
    (DESTINATION / "VERSION.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


class build_py_with_schemas(build_py):
    # os arquivos precisam existir antes de finalize_options, que lista o package_data
    def finalize_options(self):
        sync_schemas()
        super().finalize_options()


setup(cmdclass={"build_py": build_py_with_schemas})
