import argparse
import json
import sys

from . import Validator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ods-validate")
    parser.add_argument("--schemas", help="pasta dos schemas (ou ODS_SCHEMAS_DIR)")
    parser.add_argument("--topic", help="força o tópico (padrão: campo 'schema')")
    parser.add_argument("--info", action="store_true", help="mostra de onde vêm os schemas")
    parser.add_argument("files", nargs="*", help="arquivos JSON (- para stdin)")
    args = parser.parse_args(argv)
    validator = Validator(args.schemas)
    if args.info:
        for key, value in validator.schemas_version.items():
            print(f"{key}: {value}")
        if not args.files:
            return 0
    if not args.files:
        parser.error("informe ao menos um arquivo (ou use --info)")
    status = 0
    for name in args.files:
        text = sys.stdin.read() if name == "-" else open(name, encoding="utf-8").read()
        try:
            message = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"{name}: JSON inválido ({e})")
            status = 1
            continue
        errors = (
            validator.find_errors(args.topic, message)
            if args.topic
            else validator.find_message_errors(message)
        )
        if errors:
            status = 1
            print(f"{name}: INVÁLIDA")
            for e in errors:
                print("  -", e)
        else:
            print(f"{name}: ok")
    return status


if __name__ == "__main__":
    sys.exit(main())
