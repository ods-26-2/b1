// Embute os schemas do repositório b1 no pacote (build time).
// Lê ../schemas/*/*.schema.json e gera src/generated/schemas.ts com os
// schemas e o commit do b1. O pacote final não depende de arquivos externos.
import { execSync } from "node:child_process";
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const aqui = dirname(fileURLToPath(import.meta.url));
const repo = resolve(aqui, "..", "..");
const schemasDir = join(repo, "schemas");
const destino = resolve(aqui, "..", "src", "generated", "schemas.ts");

function listar(dir) {
  return readdirSync(dir).flatMap((nome) => {
    const p = join(dir, nome);
    return statSync(p).isDirectory() ? listar(p) : p.endsWith(".schema.json") ? [p] : [];
  });
}

function git(...args) {
  try {
    return execSync(`git ${args.join(" ")}`, { cwd: repo, stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim() || null;
  } catch {
    return null;
  }
}

let arquivos;
try {
  arquivos = listar(schemasDir).sort();
} catch {
  arquivos = [];
}
if (arquivos.length === 0) {
  console.error(`gerar-schemas: nenhum *.schema.json em ${schemasDir}. Rode de dentro do clone do b1.`);
  process.exit(1);
}

const itens = arquivos.map((f) => ({
  arquivo: relative(schemasDir, f).split("\\").join("/"),
  schema: JSON.parse(readFileSync(f, "utf8")),
}));
const versao = {
  commit: git("rev-parse", "HEAD"),
  descricao: git("describe", "--tags", "--always", "--dirty"),
  gerado_em: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
};

mkdirSync(dirname(destino), { recursive: true });
writeFileSync(
  destino,
  "// GERADO por scripts/gerar-schemas.mjs. Não edite.\n" +
    "export interface SchemaEmbutido { arquivo: string; schema: unknown }\n" +
    `export const SCHEMAS: SchemaEmbutido[] = ${JSON.stringify(itens, null, 1)};\n` +
    `export const VERSAO: { commit: string | null; descricao: string | null; gerado_em: string } = ${JSON.stringify(versao)};\n`,
);
console.log(`gerar-schemas: ${itens.length} schemas embutidos (${versao.descricao ?? "sem git"})`);
