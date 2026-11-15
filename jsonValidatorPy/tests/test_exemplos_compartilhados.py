"""Roda os mesmos examples/*.json que as bibliotecas TypeScript e C++ rodam."""
import json
from pathlib import Path

import pytest

from ods_validador import Validator

EXEMPLOS = Path(__file__).resolve().parents[2] / "examples"
ARQUIVOS = sorted(EXEMPLOS.glob("*.json"))

pytestmark = pytest.mark.skipif(not ARQUIVOS, reason="pasta examples/ ausente")


@pytest.fixture(scope="module")
def val():
    return Validator()


def _casos():
    for arq in ARQUIVOS:
        doc = json.loads(arq.read_text(encoding="utf-8"))
        for i, msg in enumerate(doc["valid"]):
            yield pytest.param(doc["topic"], msg, True, id=f"{doc['topic']}::valido{i}")
        for c in doc["invalid"]:
            yield pytest.param(
                doc["topic"], c["message"], False, id=f"{doc['topic']}::{c['caso']}"
            )


@pytest.mark.parametrize("topico,msg,deve_passar", list(_casos()))
def test_exemplo(val, topico, msg, deve_passar):
    erros = val.validar(topico, msg)
    assert (erros == []) is deve_passar, erros


def test_todo_topico_tem_exemplo(val):
    assert {json.loads(a.read_text())["topic"] for a in ARQUIVOS} == set(val.topicos)
