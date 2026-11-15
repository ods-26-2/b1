#!/usr/bin/env node
/** ods-validar [--schemas PASTA] [--topico T] [--info] arquivo.json [...]  (- = stdin) */
import { readFileSync } from "node:fs";
import { Validator } from "./validator";

function main(argv: string[]): number {
  let schemas: string | undefined;
  let topico: string | undefined;
  let info = false;
  const arquivos: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--schemas") schemas = argv[++i];
    else if (a === "--topico") topico = argv[++i];
    else if (a === "--info") info = true;
    else arquivos.push(a);
  }
  const val = new Validator({ dir: schemas });
  if (info) {
    for (const [k, v] of Object.entries(val.schemasVersion)) console.log(`${k}: ${v}`);
    if (arquivos.length === 0) return 0;
  }
  if (arquivos.length === 0) {
    console.error("informe ao menos um arquivo (ou use --info)");
    return 2;
  }
  let rc = 0;
  for (const nome of arquivos) {
    let msg: unknown;
    try {
      msg = JSON.parse(readFileSync(nome === "-" ? 0 : nome, "utf8"));
    } catch (e) {
      console.log(`${nome}: JSON inválido (${(e as Error).message})`);
      rc = 1;
      continue;
    }
    const erros = topico ? val.validar(topico, msg) : val.validarMensagem(msg);
    if (erros.length > 0) {
      rc = 1;
      console.log(`${nome}: INVÁLIDA`);
      for (const e of erros) console.log("  -", e);
    } else {
      console.log(`${nome}: ok`);
    }
  }
  return rc;
}

process.exit(main(process.argv.slice(2)));
