from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

ENV_PASTA = "ODS_SCHEMAS_DIR"

class ContractError(ValueError):
    def __init__(self, topico: str | None, erros: list[str]):
        self.topico = topico
        self.erros = erros
        super().__init__(f"{topico}: " + "; ".join(erros))


class Validator:
    def __init__(self, pasta: str | os.PathLike | None = None):
        pasta = pasta or os.environ.get(ENV_PASTA)
        if not pasta:
            raise ValueError(f"informe a pasta dos schemas ou defina {ENV_PASTA}")
        self.pasta = Path(pasta)
        self._por_topico: dict[str, Draft202012Validator] = {}
        self._origem: dict[str, Path] = {}

        checker = FormatChecker()
        for arq in sorted(self.pasta.rglob("*.json")):
            schema = json.loads(arq.read_text(encoding="utf-8"))
            topico = (
                schema.get("properties", {}).get("schema", {}).get("const")
            )
            if not topico:
                raise ValueError(f"{arq}: sem properties.schema.const")
            if topico in self._por_topico:
                raise ValueError(
                    f"tópico duplicado {topico}: {self._origem[topico]} e {arq}"
                )
            Draft202012Validator.check_schema(schema)
            self._por_topico[topico] = Draft202012Validator(
                schema, format_checker=checker
            )
            self._origem[topico] = arq

    @property
    def topicos(self) -> list[str]:
        return sorted(self._por_topico)

    def validar(self, topico: str, mensagem: Any) -> list[str]:
        v = self._por_topico.get(topico)
        if v is None:
            return [f"tópico desconhecido: {topico}"]
        erros = []
        for e in sorted(v.iter_errors(mensagem), key=lambda e: list(e.absolute_path)):
            onde = "/".join(str(p) for p in e.absolute_path) or "(raiz)"
            erros.append(f"{onde}: {e.message}")
        return erros

    def validar_mensagem(self, mensagem: Any) -> list[str]:
        """Descobre o tópico pelo campo ``schema`` da própria mensagem."""
        if not isinstance(mensagem, dict) or "schema" not in mensagem:
            return ["(raiz): mensagem sem o campo 'schema'"]
        return self.validar(mensagem["schema"], mensagem)

    def validate(self, mensagem: Any, topico: str | None = None) -> str:
        topico = topico or (
            mensagem.get("schema") if isinstance(mensagem, dict) else None
        )
        erros = (
            self.validar(topico, mensagem)
            if topico
            else ["(raiz): mensagem sem o campo 'schema'"]
        )
        if erros:
            raise ContractError(topico, erros)
        return topico


def publish(
    enviar: Callable[[str, bytes], Any],
    validador: Validator,
    mensagem: dict,
    topico: str | None = None,
) -> str:
    topico = validador.exigir(mensagem, topico)
    enviar(topico, json.dumps(mensagem, ensure_ascii=False).encode("utf-8"))
    return topico
