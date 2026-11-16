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
const here = dirname(fileURLToPath(import.meta.url));
const repo = join(here, "..", "..");
const cli = join(here, "..", "dist", "cli.js");
const example = (topic) => JSON.parse(readFileSync(join(repo, "examples", `${topic}.json`), "utf8")).valid[0];
const validator = new Validator();

test("carrega os schemas embutidos", () => {
  assert.equal(validator.origin, "package");
  assert.equal(validator.topics.length, 56);
  assert.equal(validator.schemasVersion.count, 56);
  assert.ok(validator.schemasVersion.generated_at);
});

test("tópico desconhecido e mensagem sem schema", () => {
  assert.match(validator.findErrors("ods.nao.existe", {})[0], /desconhecido/);
  assert.ok(validator.findMessageErrors({ producer: "x" }).length > 0);
  assert.ok(validator.findMessageErrors([]).length > 0);
});

// sem a checagem de formato, estes dois passariam em silêncio
test("uuid e date-time são checados de verdade", () => {
  const reply = example("ods.p7.move.reply");
  reply.correlation_id = "isto-nao-e-uuid";
  assert.ok(validator.findErrors("ods.p7.move.reply", reply).length > 0);
  const frame = example("ods.p4.frame");
  frame.captured_at = "ontem às 10h";
  assert.ok(validator.findErrors("ods.p4.frame", frame).length > 0);
});

test("os erros apontam o caminho do campo", () => {
  const message = example("ods.p7.move.command");
  message.payload.pan_deg = 120;
  const errors = validator.findErrors("ods.p7.move.command", message);
  assert.ok(errors.some((e) => e.startsWith("payload/pan_deg:")), errors.join("|"));
});

test("validate lança ContractError", () => {
  const message = example("ods.p7.move.command");
  assert.equal(validator.validate(message), "ods.p7.move.command");
  message.payload.pan_deg = 500;
  assert.throws(
    () => validator.validate(message),
    (e) => e instanceof ContractError && e.errors.length > 0 && e.topic === "ods.p7.move.command",
  );
});

test("publish valida antes de enviar", async () => {
  const sent = [];
  const valid = example("ods.p7.move.command");
  await publish(async (t, b) => sent.push([t, b]), validator, valid);
  assert.equal(sent[0][0], "ods.p7.move.command");
  assert.ok(Buffer.isBuffer(sent[0][1]));
  const invalid = structuredClone(valid);
  invalid.payload.pan_deg = 500;
  await assert.rejects(publish(async (t, b) => sent.push([t, b]), validator, invalid), ContractError);
  assert.equal(sent.length, 1);
});

test("opção dir vence a cópia embutida; pasta vazia dá erro claro", () => {
  assert.equal(new Validator({ dir: join(repo, "schemas") }).origin, "argument");
  assert.throws(() => new Validator({ dir: mkdtempSync(join(tmpdir(), "ods-")) }), /nenhum/);
});

test("variável ODS_SCHEMAS_DIR vence a cópia embutida", () => {
  const out = execFileSync("node", [cli, "--info"], {
    env: { ...process.env, ODS_SCHEMAS_DIR: join(repo, "schemas") },
  }).toString();
  assert.match(out, /origin: ODS_SCHEMAS_DIR/);
});

test("CLI: exit 0 para válida, 1 para inválida", () => {
  const dir = mkdtempSync(join(tmpdir(), "ods-"));
  const good = join(dir, "good.json");
  const bad = join(dir, "bad.json");
  const message = example("ods.p7.move.command");
  writeFileSync(good, JSON.stringify(message));
  message.payload.pan_deg = 120;
  writeFileSync(bad, JSON.stringify(message));
  assert.equal(spawnSync("node", [cli, good]).status, 0);
  const result = spawnSync("node", [cli, bad]);
  assert.equal(result.status, 1);
  assert.match(result.stdout.toString(), /pan_deg/);
});
