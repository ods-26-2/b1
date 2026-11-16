import json
from pathlib import Path

import pytest

from ods_validator import Validator

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FILES = sorted(EXAMPLES.glob("*.json"))

pytestmark = pytest.mark.skipif(not FILES, reason="pasta examples/ ausente")


@pytest.fixture(scope="module")
def validator():
    return Validator()


def _cases():
    for file in FILES:
        doc = json.loads(file.read_text(encoding="utf-8"))
        for i, message in enumerate(doc["valid"]):
            yield pytest.param(doc["topic"], message, True, id=f"{doc['topic']}::valid{i}")
        for c in doc["invalid"]:
            yield pytest.param(doc["topic"], c["message"], False, id=f"{doc['topic']}::{c['case']}")


@pytest.mark.parametrize("topic,message,should_pass", list(_cases()))
def test_example(validator, topic, message, should_pass):
    errors = validator.find_errors(topic, message)
    assert (errors == []) is should_pass, errors


def test_every_topic_has_examples(validator):
    assert {json.loads(f.read_text())["topic"] for f in FILES} == set(validator.topics)
