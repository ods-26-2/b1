"""Validador de mensagens do barramento (entregável B1 da TRA-1).

A chave de busca é o valor de ``properties.schema.const`` de cada schema,
que é o nome do tópico. O nome do arquivo e da pasta não importam.

Onde os schemas são procurados, nesta ordem:
  1. argumento ``Validator("pasta")``
  2. variável de ambiente ``ODS_SCHEMAS_DIR``
  3. cópia embutida no pacote (gerada no build a partir do repositório b1)
  4. o próprio repositório b1, quando o código roda de dentro do clone
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

ENV_PASTA = "ODS_SCHEMAS_DIR"
PADRAO_ARQUIVO = "*.schema.json"
PASTA_EMBUTIDA = Path(__file__).resolve().parent / "_schemas"


class ContractError(ValueError):
    """Mensagem fora do contrato. ``erros`` lista cada violação."""

    def __init__(self, topico: str | None, erros: list[str]):
        self.topico = topico
        self.erros = erros
        super().__init__(f"{topico}: " + "; ".join(erros))


def _resolver_pasta(pasta: str | os.PathLike | None) -> tuple[Path, str]:
    if pasta:
        return Path(pasta), "argumento"
    env = os.environ.get(ENV_PASTA)
    if env:
        return Path(env), ENV_PASTA
    if any(PASTA_EMBUTIDA.rglob(PADRAO_ARQUIVO)):
        return PASTA_EMBUTIDA, "pacote"
    # <repo b1>/jsonValidatorPy/src/validator.py -> parents[2] = <repo b1>
    repo = Path(__file__).resolve().parents[2]
    if any(repo.glob("*/" + PADRAO_ARQUIVO)):
        return repo, "repositório"
    raise ValueError(
        f"schemas não encontrados: informe a pasta ou defina {ENV_PASTA}"
    )


class Validator:
    def __init__(self, pasta: str | os.PathLike | None = None):
        self.pasta, self.origem = _resolver_pasta(pasta)
        self._por_topico: dict[str, Draft202012Validator] = {}
        self._arquivo: dict[str, Path] = {}
        # FormatChecker faz "uuid" e "date-time" valerem de verdade.
        # Sem ele, o jsonschema trata "format" só como anotação.
        checker = FormatChecker()
        arquivos = sorted(self.pasta.rglob(PADRAO_ARQUIVO))
        if not arquivos:
            raise ValueError(f"nenhum {PADRAO_ARQUIVO} em {self.pasta}")
        for arq in arquivos:
            schema = json.loads(arq.read_text(encoding="utf-8"))
            topico = schema.get("properties", {}).get("schema", {}).get("const")
            if not topico:
                raise ValueError(f"{arq}: sem properties.schema.const")
            if topico in self._por_topico:
                raise ValueError(
                    f"tópico duplicado {topico}: {self._arquivo[topico]} e {arq}"
                )
            Draft202012Validator.check_schema(schema)
            self._por_topico[topico] = Draft202012Validator(
                schema, format_checker=checker
            )
            self._arquivo[topico] = arq

    @property
    def topicos(self) -> list[str]:
        return sorted(self._por_topico)

    @property
    def schemas_version(self) -> dict:
        """De onde vieram os schemas e, no pacote, de qual commit do b1."""
        info = {
            "origem": self.origem,
            "pasta": str(self.pasta),
            "quantidade": len(self._por_topico),
        }
        meta = self.pasta / "VERSAO.json"
        if meta.is_file():
            info.update(json.loads(meta.read_text(encoding="utf-8")))
        return info

    def validar(self, topico: str, mensagem: Any) -> list[str]:
        """Devolve a lista de erros. Lista vazia = mensagem válida."""
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
        """Levanta ContractError se inválida. Devolve o tópico."""
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
    """Valida e só então envia. Mensagem inválida nunca chega ao broker.

    ``enviar(topico, bytes)`` é qualquer função que publica no Kafka.
    """
    topico = validador.validate(mensagem, topico)
    enviar(topico, json.dumps(mensagem, ensure_ascii=False).encode("utf-8"))
    return topico
