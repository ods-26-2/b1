// Roda os mesmos examples/*.json que as bibliotecas Python e C++ rodam.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { Validator } = require("../dist");
const aqui = dirname(fileURLToPath(import.meta.url));
const pasta = join(aqui, "..", "..", "examples");
const arquivos = readdirSync(pasta).filter((f) => f.endsWith(".json")).sort();
const val = new Validator();

test("há exemplos", () => assert.ok(arquivos.length > 0));

test("todo tópico tem arquivo de exemplos", () => {
  const doExemplos = arquivos.map((f) => JSON.parse(readFileSync(join(pasta, f), "utf8")).topic).sort();
  assert.deepEqual(doExemplos, val.topicos);
});

for (const arq of arquivos) {
  test(arq, () => {
    const doc = JSON.parse(readFileSync(join(pasta, arq), "utf8"));
    const falhas = [];
    doc.valid.forEach((msg, i) => {
      const erros = val.validar(doc.topic, msg);
      if (erros.length) falhas.push(`valid[${i}] foi recusado: ${erros.join("; ")}`);
    });
    for (const c of doc.invalid) {
      if (val.validar(doc.topic, c.message).length === 0) falhas.push(`inválido "${c.caso}" foi aceito`);
    }
    assert.deepEqual(falhas, []);
  });
}
