#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { Validator } from "./validator";

function main(argv: string[]): number {
  let schemas: string | undefined;
  let topic: string | undefined;
  let info = false;
  const files: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "--schemas") schemas = argv[++i];
    else if (arg === "--topic") topic = argv[++i];
    else if (arg === "--info") info = true;
    else files.push(arg);
  }
  const validator = new Validator({ dir: schemas });
  if (info) {
    for (const [key, value] of Object.entries(validator.schemasVersion)) console.log(`${key}: ${value}`);
    if (files.length === 0) return 0;
  }
  if (files.length === 0) {
    console.error("informe ao menos um arquivo (ou use --info)");
    return 2;
  }
  let status = 0;
  for (const name of files) {
    let message: unknown;
    try {
      message = JSON.parse(readFileSync(name === "-" ? 0 : name, "utf8"));
    } catch (e) {
      console.log(`${name}: JSON inválido (${(e as Error).message})`);
      status = 1;
      continue;
    }
    const errors = topic ? validator.findErrors(topic, message) : validator.findMessageErrors(message);
    if (errors.length > 0) {
      status = 1;
      console.log(`${name}: INVÁLIDA`);
      for (const e of errors) console.log("  -", e);
    } else {
      console.log(`${name}: ok`);
    }
  }
  return status;
}

process.exit(main(process.argv.slice(2)));
