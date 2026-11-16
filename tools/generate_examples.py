#!/usr/bin/env python3
"""Gera examples/<topic>.json a partir dos schemas: python tools/generate_examples.py"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "jsonValidatorPy" / "tests"))
sys.path.insert(0, str(ROOT / "jsonValidatorPy"))

from message_factory import generate_message  # noqa: E402
from ods_validator import Validator  # noqa: E402

SCHEMAS = ROOT / "schemas"
OUTPUT = ROOT / "examples"

# regras de valor que a mutação automática não enxerga
MANUAL_CASES = {
    "ods.p7.move.command": [
        ("pan-out-of-range", lambda m: m["payload"].update(pan_deg=91)),
        ("tilt-out-of-range", lambda m: m["payload"].update(tilt_deg=46)),
        ("zero-speed", lambda m: m["payload"].update(speed_deg_s=0)),
    ],
    "ods.p7.move.reply": [
        ("error-without-error-block", lambda m: m.update(payload={"status": "ERROR"})),
        ("unknown-status", lambda m: m["payload"].update(status="TALVEZ")),
    ],
}


def mutations(schema, valid):
    for field in schema.get("required", []):
        m = copy.deepcopy(valid)
        del m[field]
        yield f"missing-{field}", m
    for field in schema["properties"]["payload"].get("required", []):
        m = copy.deepcopy(valid)
        m["payload"].pop(field, None)
        yield f"payload-missing-{field}", m
    m = copy.deepcopy(valid)
    m["producer"] = 123
    yield "producer-wrong-type", m
    m = copy.deepcopy(valid)
    m["schema"] = "ods.outro.topico"
    yield "schema-swapped", m
    m = copy.deepcopy(valid)
    m["payload"] = "texto"
    yield "payload-not-object", m
    yield "root-array", []
    for field, prop in schema["properties"].items():
        if prop.get("format") == "uuid" and field in valid:
            m = copy.deepcopy(valid)
            m[field] = "isto-nao-e-uuid"
            yield f"{field}-not-uuid", m
        if prop.get("format") == "date-time" and field in valid:
            m = copy.deepcopy(valid)
            m[field] = "ontem as 10h"
            yield f"{field}-invalid-date", m
            # RFC 3339 exige data, hora e fuso
            m = copy.deepcopy(valid)
            m[field] = "2026-11-14T12:00:00"
            yield f"{field}-no-timezone", m
            m = copy.deepcopy(valid)
            m[field] = "2026-11-14"
            yield f"{field}-date-only", m


def main():
    validator = Validator(SCHEMAS)
    OUTPUT.mkdir(exist_ok=True)
    for old in OUTPUT.glob("*.json"):
        old.unlink()
    total_invalid = dropped = 0
    for file in sorted(SCHEMAS.rglob("*.schema.json")):
        schema = json.loads(file.read_text(encoding="utf-8"))
        topic = schema["properties"]["schema"]["const"]
        valid = generate_message(schema)
        assert validator.find_errors(topic, valid) == [], f"exemplo válido falhou: {topic}"
        cases = list(mutations(schema, valid))
        for name, change in MANUAL_CASES.get(topic, []):
            m = copy.deepcopy(valid)
            change(m)
            cases.append((name, m))
        invalid = []
        for name, message in cases:
            # só entra o que o validador Python de fato recusa
            if validator.find_errors(topic, message):
                invalid.append({"case": name, "message": message})
            else:
                dropped += 1
        total_invalid += len(invalid)
        doc = {
            "topic": topic,
            "schema_file": str(file.relative_to(SCHEMAS)).replace("\\", "/"),
            "valid": [valid],
            "invalid": invalid,
        }
        (OUTPUT / f"{topic}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    n = len(list(OUTPUT.glob("*.json")))
    print(f"{n} arquivos, {n} válidos, {total_invalid} inválidos ({dropped} mutações descartadas)")


if __name__ == "__main__":
    main()
