import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { Validator, ContractError, publish } = require("../dist");
const aqui = dirname(fileURLToPath(import.meta.url));
const repo = join(aqui, "..", "..");
const exemplo = (t) => JSON.parse(readFileSync(join(repo, "examples", `${t}.json`), "utf8")).valid[0];
const val = new Validator();

test("carrega os schemas embutidos", () => {
  assert.equal(val.origem, "pacote");
  assert.equal(val.topicos.length, 56);
  assert.equal(val.schemasVersion.quantidade, 56);
  assert.ok(val.schemasVersion.gerado_em);
});

test("tópico desconhecido e mensagem sem schema", () => {
  assert.match(val.validar("ods.nao.existe", {})[0], /desconhecido/);
  assert.ok(val.validarMensagem({ producer: "x" }).length > 0);
  assert.ok(val.validarMensagem([]).length > 0);
});

// Sem a checagem de formato, estes dois passariam em silêncio.
test("uuid e date-time são checados de verdade", () => {
  const reply = exemplo("ods.p7.move.reply");
  reply.correlation_id = "isto-nao-e-uuid";
  assert.ok(val.validar("ods.p7.move.reply", reply).length > 0);
  const frame = exemplo("ods.p4.frame");
  frame.captured_at = "ontem às 10h";
  assert.ok(val.validar("ods.p4.frame", frame).length > 0);
});

test("os erros apontam o caminho do campo", () => {
  const m = exemplo("ods.p7.move.command");
  m.payload.pan_deg = 120;
  const erros = val.validar("ods.p7.move.command", m);
  assert.ok(erros.some((e) => e.startsWith("payload/pan_deg:")), erros.join("|"));
});

test("validate levanta ContractError", () => {
  const m = exemplo("ods.p7.move.command");
  assert.equal(val.validate(m), "ods.p7.move.command");
  m.payload.pan_deg = 500;
  assert.throws(() => val.validate(m), (e) => e instanceof ContractError && e.erros.length > 0 && e.topico === "ods.p7.move.command");
});

test("publish valida antes de enviar", async () => {
  const enviados = [];
  const ok = exemplo("ods.p7.move.command");
  await publish(async (t, b) => enviados.push([t, b]), val, ok);
  assert.equal(enviados[0][0], "ods.p7.move.command");
  assert.ok(Buffer.isBuffer(enviados[0][1]));
  const ruim = structuredClone(ok);
  ruim.payload.pan_deg = 500;
  await assert.rejects(publish(async (t, b) => enviados.push([t, b]), val, ruim), ContractError);
  assert.equal(enviados.length, 1); // a inválida não foi enviada
});

test("opção dir vence a cópia embutida; pasta vazia dá erro claro", () => {
  assert.equal(new Validator({ dir: join(repo, "schemas") }).origem, "argumento");
  assert.throws(() => new Validator({ dir: mkdtempSync(join(tmpdir(), "ods-")) }), /nenhum/);
});

test("variável ODS_SCHEMAS_DIR vence a cópia embutida", () => {
  const cli = join(aqui, "..", "dist", "cli.js");
  const out = execFileSync("node", [cli, "--info"], {
    env: { ...process.env, ODS_SCHEMAS_DIR: join(repo, "schemas") },
  }).toString();
  assert.match(out, /origem: ODS_SCHEMAS_DIR/);
});

test("CLI: exit 0 para válida, 1 para inválida", () => {
  const cli = join(aqui, "..", "dist", "cli.js");
  const dir = mkdtempSync(join(tmpdir(), "ods-"));
  const bom = join(dir, "bom.json");
  const ruim = join(dir, "ruim.json");
  const m = exemplo("ods.p7.move.command");
  writeFileSync(bom, JSON.stringify(m));
  m.payload.pan_deg = 120;
  writeFileSync(ruim, JSON.stringify(m));
  assert.equal(spawnSync("node", [cli, bom]).status, 0);
  const r = spawnSync("node", [cli, ruim]);
  assert.equal(r.status, 1);
  assert.match(r.stdout.toString(), /pan_deg/);
});
