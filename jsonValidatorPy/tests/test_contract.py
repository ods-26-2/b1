import copy
import json

import pytest

from ods_validator import ContractError, Validator, publish
from message_factory import generate, generate_message

FILES = sorted(Validator().directory.rglob("*.schema.json"))


@pytest.fixture(scope="module")
def validator():
    return Validator()


def _load(file):
    return json.loads(file.read_text(encoding="utf-8"))


def _schema_named(stem):
    return _load(next(f for f in FILES if f.stem == stem))


@pytest.fixture(params=FILES, ids=lambda f: f"{f.parent.name}/{f.stem}")
def case(request):
    schema = _load(request.param)
    return schema["properties"]["schema"]["const"], schema, generate_message(schema)


def test_loads_all_without_duplicates(validator):
    assert len(validator.topics) == len(FILES) > 0


def test_schemas_version(validator):
    info = validator.schemas_version
    assert info["count"] == len(FILES)
    assert info["origin"] in {"package", "repository", "ODS_SCHEMAS_DIR"}


def test_argument_wins_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ODS_SCHEMAS_DIR", str(tmp_path))
    assert Validator(FILES[0].parent).origin == "argument"


def test_environment_wins_over_default(tmp_path, monkeypatch):
    monkeypatch.setenv("ODS_SCHEMAS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="nenhum"):
        Validator()


def test_empty_directory_gives_clear_error(tmp_path):
    with pytest.raises(ValueError, match="nenhum"):
        Validator(tmp_path)


def test_valid_example_passes(validator, case):
    topic, _, message = case
    assert validator.find_errors(topic, message) == []


def test_missing_required_field_fails(validator, case):
    topic, schema, message = case
    for field in schema["required"]:
        broken = copy.deepcopy(message)
        del broken[field]
        assert validator.find_errors(topic, broken), f"aceitou sem '{field}'"


def test_missing_required_payload_field_fails(validator, case):
    topic, schema, message = case
    for field in schema["properties"]["payload"].get("required", []):
        broken = copy.deepcopy(message)
        broken["payload"].pop(field, None)
        assert validator.find_errors(topic, broken), f"aceitou payload sem '{field}'"


def test_wrong_envelope_type_fails(validator, case):
    topic, _, message = case
    broken = copy.deepcopy(message)
    broken["producer"] = 123
    assert validator.find_errors(topic, broken)


def test_swapped_topic_fails(validator, case):
    topic, _, message = case
    other = next(t for t in validator.topics if t != topic)
    assert validator.find_errors(other, message)


def test_non_object_message_fails(validator, case):
    topic, _, _ = case
    assert validator.find_errors(topic, [])
    assert validator.find_errors(topic, "texto")


def test_unknown_topic(validator):
    assert "desconhecido" in validator.find_errors("ods.nao.existe", {})[0]


def test_message_without_schema_field(validator):
    assert validator.find_message_errors({"producer": "x"})


# sem o FormatChecker, estes dois passariam em silêncio
def test_invalid_uuid_fails(validator):
    message = generate(_schema_named("moveReply.schema"))
    message["correlation_id"] = "isto-nao-e-uuid"
    assert validator.find_errors("ods.p7.move.reply", message)


def test_invalid_date_time_fails(validator):
    message = generate(_schema_named("frameEvent.schema"))
    message["captured_at"] = "ontem às 10h"
    assert validator.find_errors("ods.p4.frame", message)


def _move_command():
    return generate(_schema_named("moveCommand.schema"))


def test_pan_out_of_range_fails(validator):
    message = _move_command()
    message["payload"]["pan_deg"] = 91
    assert validator.find_errors("ods.p7.move.command", message)


def test_error_reply_requires_error_block(validator):
    message = generate(_schema_named("moveReply.schema"))
    message["payload"] = {"status": "ERROR"}
    assert validator.find_errors("ods.p7.move.reply", message)
    message["payload"]["error"] = {"code": "OUT_OF_RANGE", "message": "fora do limite"}
    assert validator.find_errors("ods.p7.move.reply", message) == []


def test_publish_validates_before_sending(validator):
    sent = []
    valid = _move_command()
    publish(lambda t, b: sent.append((t, b)), validator, valid)
    assert sent[0][0] == "ods.p7.move.command"

    invalid = copy.deepcopy(valid)
    invalid["payload"]["pan_deg"] = 500
    with pytest.raises(ContractError) as e:
        publish(lambda t, b: sent.append((t, b)), validator, invalid)
    assert "pan_deg" in str(e.value)
    assert len(sent) == 1
