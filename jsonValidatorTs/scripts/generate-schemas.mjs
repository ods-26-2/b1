import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const schemasDir = join(repo, "schemas");
const destination = resolve(here, "..", "src", "generated", "schemas.ts");

function listFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? listFiles(path) : path.endsWith(".schema.json") ? [path] : [];
  });
}

function git(...args) {
  if (!existsSync(join(repo, ".git"))) return null;
  try {
    return execSync(`git ${args.join(" ")}`, { cwd: repo, stdio: ["ignore", "pipe", "ignore"] })
      .toString()
      .trim() || null;
  } catch {
    return null;
  }
}

let files;
try {
  files = listFiles(schemasDir).sort();
} catch {
  files = [];
}
if (files.length === 0) {
  console.error(`generate-schemas: nenhum *.schema.json em ${schemasDir}. Rode de dentro do clone do b1.`);
  process.exit(1);
}

const items = files.map((file) => ({
  file: relative(schemasDir, file).split("\\").join("/"),
  schema: JSON.parse(readFileSync(file, "utf8")),
}));
const version = {
  commit: git("rev-parse", "HEAD"),
  description: git("describe", "--tags", "--always", "--dirty"),
  generated_at: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
};

mkdirSync(dirname(destination), { recursive: true });
writeFileSync(
  destination,
  "// GERADO por scripts/generate-schemas.mjs. Não edite.\n" +
    "export interface EmbeddedSchema { file: string; schema: unknown }\n" +
    `export const SCHEMAS: EmbeddedSchema[] = ${JSON.stringify(items, null, 1)};\n` +
    `export const VERSION: { commit: string | null; description: string | null; generated_at: string } = ${JSON.stringify(version)};\n`,
);
console.log(`generate-schemas: ${items.length} schemas embutidos (${version.description ?? "sem git"})`);
