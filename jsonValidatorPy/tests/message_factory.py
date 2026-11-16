from jsonschema import Draft202012Validator, FormatChecker

UUID = "123e4567-e89b-42d3-a456-426614174000"
DATE_TIME = "2026-11-14T12:00:00Z"
URI = "https://exemplo.local/recurso"
# campos com "pattern" que o gerador não sabe inventar
PATTERNS = {"license_plate": "ABC1234", "actor": "user:ana"}
# regras aninhadas (allOf/anyOf dentro de then) que o gerador não alcança
MANUAL_PAYLOADS = {
    "ods.s5.heatmap.reply": {
        "status": "OK",
        "grid_width": 1,
        "grid_height": 1,
        "cell_size_m": 0.5,
        "origin": [0, 0],
        "cells": [[0]],
    },
}


def generate(schema: dict):
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "type" not in schema and "properties" not in schema:
        for key in ("oneOf", "anyOf"):
            if key in schema:
                return generate(schema[key][0])
    type_ = schema.get("type")
    if isinstance(type_, list):
        type_ = next((t for t in type_ if t != "null"), "null")
        schema = {**schema, "type": type_}
    if type_ == "object" or "properties" in schema:
        props = schema.get("properties", {})
        obj = {k: _field(k, props[k]) for k in schema.get("required", []) if k in props}
        for key in ("oneOf", "anyOf"):
            branches = schema.get(key, [])
            if branches and not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(obj):
                for k in branches[0].get("required", []):
                    obj.setdefault(k, _field(k, props[k]))
        for rule in schema.get("allOf", []):
            condition, consequence = rule.get("if"), rule.get("then")
            if condition is None or consequence is None:
                continue
            if Draft202012Validator(condition).is_valid(obj):
                for k in consequence.get("required", []):
                    if k not in obj:
                        obj[k] = _field(k, props[k])
        return obj
    if type_ == "array":
        item = generate(schema["items"]) if "items" in schema else "x"
        # o tamanho pode vir de minItems/maxItems ou de um anyOf/oneOf
        targets = [schema] + schema.get("anyOf", []) + schema.get("oneOf", [])
        sizes = []
        for target in targets:
            sizes += [target.get("minItems", 0), target.get("maxItems", 0)]
        for n in dict.fromkeys(sizes):
            candidate = [item for _ in range(n)]
            if Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(candidate):
                return candidate
        return [item]
    if type_ == "string":
        fmt = schema.get("format")
        if fmt == "uuid":
            return UUID
        if fmt == "date-time":
            return DATE_TIME
        if fmt == "uri":
            return URI
        return "x" * max(1, schema.get("minLength", 0))
    if type_ == "integer":
        value = int(schema.get("minimum", 0))
        if "exclusiveMinimum" in schema:
            value = int(schema["exclusiveMinimum"]) + 1
        return max(value, int(schema.get("minimum", value)))
    if type_ == "number":
        if "exclusiveMinimum" in schema:
            return schema["exclusiveMinimum"] + 1
        return schema.get("minimum", 0)
    if type_ == "boolean":
        return False
    if type_ == "null":
        return None
    return "x"


def generate_message(schema: dict):
    message = generate(schema)
    topic = schema["properties"]["schema"]["const"]
    if topic in MANUAL_PAYLOADS:
        message["payload"] = MANUAL_PAYLOADS[topic]
    return message


def _field(name: str, sub: dict):
    if "pattern" in sub and name in PATTERNS:
        return PATTERNS[name]
    return generate(sub)
