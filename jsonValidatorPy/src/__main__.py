"""ods-validar [--schemas PASTA] arquivo.json [...]  (use - para stdin)"""
import argparse
import json
import sys

from . import Validador


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ods-validar")
    ap.add_argument("--schemas", help="pasta dos schemas (ou ODS_SCHEMAS_DIR)")
    ap.add_argument("--topico", help="força o tópico (padrão: campo 'schema')")
    ap.add_argument("arquivos", nargs="+")
    a = ap.parse_args(argv)
    val = Validador(a.schemas)
    rc = 0
    for nome in a.arquivos:
        txt = sys.stdin.read() if nome == "-" else open(nome, encoding="utf-8").read()
        try:
            msg = json.loads(txt)
        except json.JSONDecodeError as e:
            print(f"{nome}: JSON inválido ({e})")
            rc = 1
            continue
        erros = val.validar(a.topico, msg) if a.topico else val.validar_mensagem(msg)
        if erros:
            rc = 1
            print(f"{nome}: INVÁLIDA")
            for e in erros:
                print("  -", e)
        else:
            print(f"{nome}: ok")
    return rc


if __name__ == "__main__":
    sys.exit(main())
