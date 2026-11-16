import Ajv2020, { ErrorObject, ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { SCHEMAS, VERSION } from "./generated/schemas";

export const ENV_SCHEMAS_DIR = "ODS_SCHEMAS_DIR";
const SUFFIX = ".schema.json";

export class ContractError extends Error {
  constructor(public readonly topic: string | null, public readonly errors: string[]) {
    super(`${topic}: ${errors.join("; ")}`);
    this.name = "ContractError";
    Object.setPrototypeOf(this, ContractError.prototype);
  }
}

export interface ValidatorOptions {
  dir?: string;
}

interface Item {
  file: string;
  schema: any;
}

function readDirectory(dir: string): { items: Item[]; version: Record<string, unknown> } {
  // require tardio: o resto da biblioteca não depende de fs (serve a bundlers)
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const fs = require("node:fs") as typeof import("node:fs");
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const path = require("node:path") as typeof import("node:path");
  const found: string[] = [];
  const walk = (current: string) => {
    for (const name of fs.readdirSync(current).sort()) {
      const full = path.join(current, name);
      if (fs.statSync(full).isDirectory()) walk(full);
      else if (name.endsWith(SUFFIX)) found.push(full);
    }
  };
  walk(dir);
  const items = found.map((full) => ({
    file: path.relative(dir, full).split(path.sep).join("/"),
    schema: JSON.parse(fs.readFileSync(full, "utf8")),
  }));
  const meta = path.join(dir, "VERSION.json");
  const version = fs.existsSync(meta) ? JSON.parse(fs.readFileSync(meta, "utf8")) : {};
  return { items, version };
}

function formatError(e: ErrorObject): string {
  const path = e.instancePath.replace(/^\//, "");
  return `${path === "" ? "(raiz)" : path}: ${e.message ?? "inválido"}`;
}

function schemaField(message: unknown): unknown {
  return typeof message === "object" && message !== null && !Array.isArray(message)
    ? (message as any).schema
    : undefined;
}

export class Validator {
  readonly origin: string;
  readonly directory: string | null;
  private readonly byTopic = new Map<string, ValidateFunction>();
  private readonly fileOf = new Map<string, string>();
  private readonly meta: Record<string, unknown>;

  constructor(options: ValidatorOptions = {}) {
    const env = typeof process !== "undefined" ? process.env[ENV_SCHEMAS_DIR] : undefined;
    let items: Item[];
    if (options.dir) {
      ({ items, version: this.meta } = readDirectory(options.dir));
      this.origin = "argument";
      this.directory = options.dir;
    } else if (env) {
      ({ items, version: this.meta } = readDirectory(env));
      this.origin = ENV_SCHEMAS_DIR;
      this.directory = env;
    } else {
      items = SCHEMAS as Item[];
      this.meta = { ...VERSION };
      this.origin = "package";
      this.directory = null;
    }
    if (items.length === 0) {
      throw new Error(`nenhum *${SUFFIX} em ${this.directory ?? "(pacote)"}`);
    }

    // strictTypes/strictRequired desligados: os schemas usam type em lista e
    // then.required de campos definidos no nível acima, ambos válidos
    const ajv = new Ajv2020({ allErrors: true, strict: true, strictTypes: false, strictRequired: false });
    addFormats(ajv); // sem isso, uuid e date-time não seriam validados
    for (const { file, schema } of items) {
      const topic: unknown = schema?.properties?.schema?.const;
      if (typeof topic !== "string" || topic === "") {
        throw new Error(`${file}: sem properties.schema.const`);
      }
      if (this.byTopic.has(topic)) {
        throw new Error(`tópico duplicado ${topic}: ${this.fileOf.get(topic)} e ${file}`);
      }
      this.byTopic.set(topic, ajv.compile(schema));
      this.fileOf.set(topic, file);
    }
  }

  get topics(): string[] {
    return [...this.byTopic.keys()].sort();
  }

  get schemasVersion(): Record<string, unknown> {
    return {
      origin: this.origin,
      directory: this.directory,
      count: this.byTopic.size,
      ...this.meta,
    };
  }

  findErrors(topic: string, message: unknown): string[] {
    const validate = this.byTopic.get(topic);
    if (!validate) return [`tópico desconhecido: ${topic}`];
    if (validate(message)) return [];
    return [...(validate.errors ?? [])].map(formatError).sort();
  }

  findMessageErrors(message: unknown): string[] {
    const topic = schemaField(message);
    if (topic === undefined) return ["(raiz): mensagem sem o campo 'schema'"];
    return this.findErrors(String(topic), message);
  }

  validate(message: unknown, topic?: string): string {
    const resolved = topic ?? schemaField(message);
    const errors =
      typeof resolved === "string"
        ? this.findErrors(resolved, message)
        : ["(raiz): mensagem sem o campo 'schema'"];
    if (errors.length > 0) throw new ContractError(typeof resolved === "string" ? resolved : null, errors);
    return resolved as string;
  }
}

export type Send = (topic: string, data: Buffer) => unknown | Promise<unknown>;

export async function publish(
  send: Send,
  validator: Validator,
  message: unknown,
  topic?: string,
): Promise<string> {
  const resolved = validator.validate(message, topic);
  await send(resolved, Buffer.from(JSON.stringify(message), "utf8"));
  return resolved;
}
