import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { Validator } = require("../dist");
const here = dirname(fileURLToPath(import.meta.url));
const examplesDir = join(here, "..", "..", "examples");
const files = readdirSync(examplesDir).filter((f) => f.endsWith(".json")).sort();
const validator = new Validator();

test("há exemplos", () => assert.ok(files.length > 0));

test("todo tópico tem arquivo de exemplos", () => {
  const topics = files.map((f) => JSON.parse(readFileSync(join(examplesDir, f), "utf8")).topic).sort();
  assert.deepEqual(topics, validator.topics);
});

for (const file of files) {
  test(file, () => {
    const doc = JSON.parse(readFileSync(join(examplesDir, file), "utf8"));
    const failures = [];
    doc.valid.forEach((message, i) => {
      const errors = validator.findErrors(doc.topic, message);
      if (errors.length) failures.push(`valid[${i}] foi recusado: ${errors.join("; ")}`);
    });
    for (const c of doc.invalid) {
      if (validator.findErrors(doc.topic, c.message).length === 0) failures.push(`inválido "${c.case}" foi aceito`);
    }
    assert.deepEqual(failures, []);
  });
}
