#!/usr/bin/env python3
"""Gera examples/<topico>.json a partir dos schemas.

Cada arquivo tem "valid" (devem passar) e "invalid" (devem falhar). As três
bibliotecas (Python, TypeScript, C++) rodam os mesmos arquivos nos testes.

Os inválidos nascem de mutações do exemplo válido e só entram se o
validador Python realmente os recusa, então todo caso listado é, de fato,
uma violação do contrato. Rode de novo depois de mudar um schema.

    python tools/gerar_exemplos.py
"""
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "jsonValidatorPy" / "tests"))
sys.path.insert(0, str(RAIZ / "jsonValidatorPy"))

from exemplos import gerar_mensagem  # noqa: E402
from ods_validador import Validator  # noqa: E402

SCHEMAS = RAIZ / "schemas"
SAIDA = RAIZ / "examples"

# Casos escritos à mão para regras de valor que a mutação automática não vê.
# topico -> [(nome, função que altera o exemplo válido)]
MANUAIS = {
    "ods.p7.move.command": [
        ("pan-fora-do-limite", lambda m: m["payload"].update(pan_deg=91)),
        ("tilt-fora-do-limite", lambda m: m["payload"].update(tilt_deg=46)),
        ("velocidade-zero", lambda m: m["payload"].update(speed_deg_s=0)),
    ],
    "ods.p7.move.reply": [
        ("erro-sem-bloco-error", lambda m: m.update(payload={"status": "ERROR"})),
        ("status-desconhecido", lambda m: m["payload"].update(status="TALVEZ")),
    ],
}


def mutacoes(schema, valido):
    req = schema.get("required", [])
    for campo in req:
        m = copy.deepcopy(valido)
        del m[campo]
        yield f"sem-{campo}", m
    for campo in schema["properties"]["payload"].get("required", []):
        m = copy.deepcopy(valido)
        m["payload"].pop(campo, None)
        yield f"payload-sem-{campo}", m
    m = copy.deepcopy(valido)
    m["producer"] = 123
    yield "producer-tipo-errado", m
    m = copy.deepcopy(valido)
    m["schema"] = "ods.outro.topico"
    yield "schema-trocado", m
    m = copy.deepcopy(valido)
    m["payload"] = "texto"
    yield "payload-nao-objeto", m
    yield "raiz-array", []
    for campo, prop in schema["properties"].items():
        if prop.get("format") == "uuid" and campo in valido:
            m = copy.deepcopy(valido)
            m[campo] = "isto-nao-e-uuid"
            yield f"{campo}-nao-e-uuid", m
        if prop.get("format") == "date-time" and campo in valido:
            m = copy.deepcopy(valido)
            m[campo] = "ontem as 10h"
            yield f"{campo}-data-invalida", m
            # quase certas: o RFC 3339 exige data, hora E fuso
            m = copy.deepcopy(valido)
            m[campo] = "2026-11-14T12:00:00"
            yield f"{campo}-sem-fuso", m
            m = copy.deepcopy(valido)
            m[campo] = "2026-11-14"
            yield f"{campo}-so-data", m


def main():
    val = Validator(SCHEMAS)
    SAIDA.mkdir(exist_ok=True)
    for antigo in SAIDA.glob("*.json"):
        antigo.unlink()
    total_inv = descartados = 0
    for arq in sorted(SCHEMAS.rglob("*.schema.json")):
        schema = json.loads(arq.read_text(encoding="utf-8"))
        topico = schema["properties"]["schema"]["const"]
        valido = gerar_mensagem(schema)
        assert val.validar(topico, valido) == [], f"exemplo válido falhou: {topico}"
        casos = list(mutacoes(schema, valido))
        for nome, fn in MANUAIS.get(topico, []):
            m = copy.deepcopy(valido)
            fn(m)
            casos.append((nome, m))
        invalidos = []
        for nome, msg in casos:
            if val.validar(topico, msg):
                invalidos.append({"caso": nome, "message": msg})
            else:
                descartados += 1  # a mutação não violou o contrato
        total_inv += len(invalidos)
        doc = {
            "topic": topico,
            "schema_file": str(arq.relative_to(SCHEMAS)).replace("\\", "/"),
            "valid": [valido],
            "invalid": invalidos,
        }
        (SAIDA / f"{topico}.json").write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    n = len(list(SAIDA.glob("*.json")))
    print(f"{n} arquivos, {n} válidos, {total_inv} inválidos "
          f"({descartados} mutações descartadas por não violarem o contrato)")


if __name__ == "__main__":
    main()
