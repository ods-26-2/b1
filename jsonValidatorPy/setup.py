"""Embute os schemas do repositório b1 dentro do pacote (build time).

Fluxo: ``pip install ./jsonValidatorPy`` ou ``pip wheel`` a partir do clone
copiam ``../schemas/*/*.schema.json`` para ``src/_schemas`` e gravam ``VERSAO.json``
com o commit do b1. Quem instala o wheel não precisa de mais nada.

Se ``../schemas`` não tiver schemas (build a partir de um sdist), usa a cópia que o
sdist já trouxe em ``src/_schemas``.
"""
import datetime
import json
import shutil
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

AQUI = Path(__file__).resolve().parent
REPO = AQUI.parent
SCHEMAS = REPO / "schemas"
DESTINO = AQUI / "src" / "_schemas"


def _git(*args):
    try:
        r = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, check=True
        )
        return r.stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def sincronizar_schemas():
    origem = sorted(SCHEMAS.glob("*/*.schema.json"))
    if not origem:
        if any(DESTINO.rglob("*.schema.json")):
            return  # vindo de um sdist: a cópia já está aqui
        raise SystemExit(
            "setup.py: nenhum *.schema.json em ../schemas nem em src/_schemas. "
            "Rode o build de dentro do clone do repositório b1."
        )
    shutil.rmtree(DESTINO, ignore_errors=True)
    for arq in origem:
        alvo = DESTINO / arq.parent.name / arq.name
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(arq, alvo)
    meta = {
        "commit": _git("rev-parse", "HEAD"),
        "descricao": _git("describe", "--tags", "--always", "--dirty"),
        "gerado_em": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
    }
    (DESTINO / "VERSAO.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


class build_py_com_schemas(build_py):
    # finalize_options é onde o setuptools lista os package_data; os arquivos
    # precisam existir antes disso.
    def finalize_options(self):
        sincronizar_schemas()
        super().finalize_options()


setup(cmdclass={"build_py": build_py_com_schemas})
