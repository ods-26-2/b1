"""Gera uma mensagem mínima válida a partir de um JSON Schema.

Cobre o que os schemas da Especificação 1.0 usam: const, enum, tipos
básicos, minimum/maximum, format uuid/date-time, arrays, allOf com if/then.
Se algum schema usar algo fora disso, o teste falha com o nome do arquivo
em vez de passar em silêncio.
"""
from jsonschema import Draft202012Validator, FormatChecker

UUID = "123e4567-e89b-42d3-a456-426614174000"
URI = "https://exemplo.local/recurso"
# campos com "pattern" que o gerador não sabe inventar: valor escrito à mão
PADROES = {"license_plate": "ABC1234", "actor": "user:ana"}
DATA = "2026-11-14T12:00:00Z"


def gerar(s: dict):
    if "const" in s:
        return s["const"]
    if "enum" in s:
        return s["enum"][0]
    if "type" not in s and "properties" not in s:
        for chave in ("oneOf", "anyOf"):
            if chave in s:
                return gerar(s[chave][0])
    t = s.get("type")
    if isinstance(t, list):  # ex.: ["array", "null"] -> usa o primeiro não nulo
        t = next((x for x in t if x != "null"), "null")
        s = {**s, "type": t}
    if t == "object" or "properties" in s:
        props = s.get("properties", {})
        obj = {k: _campo(k, props[k]) for k in s.get("required", []) if k in props}
        # oneOf/anyOf em que cada ramo só exige campos: completa o primeiro ramo
        for chave in ("oneOf", "anyOf"):
            ramos = s.get(chave, [])
            if ramos and not Draft202012Validator(s, format_checker=FormatChecker()).is_valid(obj):
                for k in ramos[0].get("required", []):
                    obj.setdefault(k, _campo(k, props[k]))
        for regra in s.get("allOf", []):
            se, entao = regra.get("if"), regra.get("then")
            if se is None or entao is None:
                continue
            if Draft202012Validator(se).is_valid(obj):
                for k in entao.get("required", []):
                    if k not in obj:
                        obj[k] = _campo(k, props[k])
        return obj
    if t == "array":
        item = gerar(s["items"]) if "items" in s else "x"
        # tamanhos candidatos: o schema pode restringir por minItems/maxItems
        # ou por anyOf/oneOf (ex.: vazio OU exatamente 33 pontos)
        alvos = [s] + s.get("anyOf", []) + s.get("oneOf", [])
        tamanhos = []
        for a in alvos:
            tamanhos += [a.get("minItems", 0), a.get("maxItems", 0)]
        for n in dict.fromkeys(tamanhos):
            cand = [item for _ in range(n)]
            if Draft202012Validator(s, format_checker=FormatChecker()).is_valid(cand):
                return cand
        return [item]
    if t == "string":
        f = s.get("format")
        if f == "uuid":
            return UUID
        if f == "date-time":
            return DATA
        if f == "uri":
            return URI
        return "x" * max(1, s.get("minLength", 0))
    if t == "integer":
        v = int(s.get("minimum", 0))
        if "exclusiveMinimum" in s:
            v = int(s["exclusiveMinimum"]) + 1
        return max(v, int(s.get("minimum", v)))
    if t == "number":
        if "exclusiveMinimum" in s:
            return s["exclusiveMinimum"] + 1
        return s.get("minimum", 0)
    if t == "boolean":
        return False
    if t == "null":
        return None
    return "x"  # sem tipo: aceita qualquer coisa


def _campo(nome: str, sub: dict):
    if "pattern" in sub and nome in PADROES:
        return PADROES[nome]
    return gerar(sub)


# Payloads escritos à mão onde as regras aninhadas (allOf/anyOf dentro de
# then) passam do que o gerador alcança. Só o payload; o envelope é gerado.
PAYLOAD_MANUAL = {
    "ods.s5.heatmap.reply": {
        "status": "OK",
        "grid_width": 1,
        "grid_height": 1,
        "cell_size_m": 0.5,
        "origin": [0, 0],
        "cells": [[0]],
    },
}


def gerar_mensagem(schema: dict):
    msg = gerar(schema)
    topico = schema["properties"]["schema"]["const"]
    if topico in PAYLOAD_MANUAL:
        msg["payload"] = PAYLOAD_MANUAL[topico]
    return msg
