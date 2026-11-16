from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

ENV_SCHEMAS_DIR = "ODS_SCHEMAS_DIR"
FILE_PATTERN = "*.schema.json"
EMBEDDED_DIR = Path(__file__).resolve().parent / "_schemas"


class ContractError(ValueError):
    def __init__(self, topic: str | None, errors: list[str]):
        self.topic = topic
        self.errors = errors
        super().__init__(f"{topic}: " + "; ".join(errors))


def _resolve_directory(directory: str | os.PathLike | None) -> tuple[Path, str]:
    if directory:
        return Path(directory), "argument"
    env = os.environ.get(ENV_SCHEMAS_DIR)
    if env:
        return Path(env), ENV_SCHEMAS_DIR
    schemas = Path(__file__).resolve().parents[2] / "schemas"
    if any(schemas.glob("*/" + FILE_PATTERN)):
        return schemas, "repository"
    if any(EMBEDDED_DIR.rglob(FILE_PATTERN)):
        return EMBEDDED_DIR, "package"
    raise ValueError(
        f"schemas não encontrados: informe a pasta ou defina {ENV_SCHEMAS_DIR}"
    )


class Validator:
    def __init__(self, directory: str | os.PathLike | None = None):
        self.directory, self.origin = _resolve_directory(directory)
        self._by_topic: dict[str, Draft202012Validator] = {}
        self._file_of: dict[str, Path] = {}
        # sem o FormatChecker, "uuid" e "date-time" não seriam validados
        checker = FormatChecker()
        files = sorted(self.directory.rglob(FILE_PATTERN))
        if not files:
            raise ValueError(f"nenhum {FILE_PATTERN} em {self.directory}")
        for file in files:
            schema = json.loads(file.read_text(encoding="utf-8"))
            topic = schema.get("properties", {}).get("schema", {}).get("const")
            if not topic:
                raise ValueError(f"{file}: sem properties.schema.const")
            if topic in self._by_topic:
                raise ValueError(
                    f"tópico duplicado {topic}: {self._file_of[topic]} e {file}"
                )
            Draft202012Validator.check_schema(schema)
            self._by_topic[topic] = Draft202012Validator(schema, format_checker=checker)
            self._file_of[topic] = file

    @property
    def topics(self) -> list[str]:
        return sorted(self._by_topic)

    @property
    def schemas_version(self) -> dict:
        info = {
            "origin": self.origin,
            "directory": str(self.directory),
            "count": len(self._by_topic),
        }
        meta = self.directory / "VERSION.json"
        if meta.is_file():
            info.update(json.loads(meta.read_text(encoding="utf-8")))
        return info

    def find_errors(self, topic: str, message: Any) -> list[str]:
        validator = self._by_topic.get(topic)
        if validator is None:
            return [f"tópico desconhecido: {topic}"]
        errors = []
        for e in sorted(validator.iter_errors(message), key=lambda e: list(e.absolute_path)):
            where = "/".join(str(p) for p in e.absolute_path) or "(raiz)"
            errors.append(f"{where}: {e.message}")
        return errors

    def find_message_errors(self, message: Any) -> list[str]:
        if not isinstance(message, dict) or "schema" not in message:
            return ["(raiz): mensagem sem o campo 'schema'"]
        return self.find_errors(message["schema"], message)

    def validate(self, message: Any, topic: str | None = None) -> str:
        topic = topic or (message.get("schema") if isinstance(message, dict) else None)
        errors = (
            self.find_errors(topic, message)
            if topic
            else ["(raiz): mensagem sem o campo 'schema'"]
        )
        if errors:
            raise ContractError(topic, errors)
        return topic


def publish(
    send: Callable[[str, bytes], Any],
    validator: Validator,
    message: dict,
    topic: str | None = None,
) -> str:
    topic = validator.validate(message, topic)
    send(topic, json.dumps(message, ensure_ascii=False).encode("utf-8"))
    return topic
