import Ajv2020, { ErrorObject, ValidateFunction } from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { SCHEMAS, VERSAO } from "./generated/schemas";

export const ENV_PASTA = "ODS_SCHEMAS_DIR";
const SUFIXO = ".schema.json";

export class ContractError extends Error {
  constructor(public readonly topico: string | null, public readonly erros: string[]) {
    super(`${topico}: ${erros.join("; ")}`);
    this.name = "ContractError";
    Object.setPrototypeOf(this, ContractError.prototype);
  }
}

export interface ValidatorOptions {
  dir?: string;
}

interface Item {
  arquivo: string;
  schema: any;
}

function lerPasta(dir: string): { itens: Item[]; versao: Record<string, unknown> } {
  // require tardio: o resto da biblioteca não depende de fs (serve a bundlers)
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const fs = require("node:fs") as typeof import("node:fs");
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const path = require("node:path") as typeof import("node:path");
  const achados: string[] = [];
  const andar = (d: string) => {
    for (const nome of fs.readdirSync(d).sort()) {
      const p = path.join(d, nome);
      if (fs.statSync(p).isDirectory()) andar(p);
      else if (nome.endsWith(SUFIXO)) achados.push(p);
    }
  };
  andar(dir);
  const itens = achados.map((p) => ({
    arquivo: path.relative(dir, p).split(path.sep).join("/"),
    schema: JSON.parse(fs.readFileSync(p, "utf8")),
  }));
  const meta = path.join(dir, "VERSAO.json");
  const versao = fs.existsSync(meta) ? JSON.parse(fs.readFileSync(meta, "utf8")) : {};
  return { itens, versao };
}

function formatar(e: ErrorObject): string {
  const base = e.instancePath.replace(/^\//, "");
  const onde = base === "" ? "(raiz)" : base;
  return `${onde}: ${e.message ?? "inválido"}`;
}

export class Validator {
  readonly origem: string;
  readonly pasta: string | null;
  private readonly porTopico = new Map<string, ValidateFunction>();
  private readonly arquivoDe = new Map<string, string>();
  private readonly meta: Record<string, unknown>;

  constructor(opcoes: ValidatorOptions = {}) {
    const env = typeof process !== "undefined" ? process.env[ENV_PASTA] : undefined;
    let itens: Item[];
    if (opcoes.dir) {
      ({ itens, versao: this.meta } = lerPasta(opcoes.dir));
      this.origem = "argumento";
      this.pasta = opcoes.dir;
    } else if (env) {
      ({ itens, versao: this.meta } = lerPasta(env));
      this.origem = ENV_PASTA;
      this.pasta = env;
    } else {
      itens = SCHEMAS as Item[];
      this.meta = { ...VERSAO };
      this.origem = "pacote";
      this.pasta = null;
    }
    if (itens.length === 0) {
      throw new Error(`nenhum *${SUFIXO} em ${this.pasta ?? "(pacote)"}`);
    }

    // strict: schemas com palavra desconhecida falham na carga, não em silêncio.
    // strictTypes/strictRequired off: os schemas usam type em lista e `then.required`
    // de campos definidos no nível acima; ambos são JSON Schema válido.
    const ajv = new Ajv2020({ allErrors: true, strict: true, strictTypes: false, strictRequired: false });
    addFormats(ajv); // faz uuid, date-time e uri valerem de verdade
    for (const { arquivo, schema } of itens) {
      const topico: unknown = schema?.properties?.schema?.const;
      if (typeof topico !== "string" || topico === "") {
        throw new Error(`${arquivo}: sem properties.schema.const`);
      }
      if (this.porTopico.has(topico)) {
        throw new Error(`tópico duplicado ${topico}: ${this.arquivoDe.get(topico)} e ${arquivo}`);
      }
      this.porTopico.set(topico, ajv.compile(schema));
      this.arquivoDe.set(topico, arquivo);
    }
  }

  get topicos(): string[] {
    return [...this.porTopico.keys()].sort();
  }

  /** De onde vieram os schemas e, no pacote, de qual commit do b1. */
  get schemasVersion(): Record<string, unknown> {
    return {
      origem: this.origem,
      pasta: this.pasta,
      quantidade: this.porTopico.size,
      ...this.meta,
    };
  }

  /** Devolve a lista de erros. Lista vazia = mensagem válida. */
  validar(topico: string, mensagem: unknown): string[] {
    const v = this.porTopico.get(topico);
    if (!v) return [`tópico desconhecido: ${topico}`];
    if (v(mensagem)) return [];
    return [...(v.errors ?? [])].map(formatar).sort();
  }

  /** Descobre o tópico pelo campo "schema" da própria mensagem. */
  validarMensagem(mensagem: unknown): string[] {
    const t = (mensagem as any)?.schema;
    if (typeof mensagem !== "object" || mensagem === null || Array.isArray(mensagem) || t === undefined) {
      return ["(raiz): mensagem sem o campo 'schema'"];
    }
    return this.validar(String(t), mensagem);
  }

  /** Levanta ContractError se inválida. Devolve o tópico. */
  validate(mensagem: unknown, topico?: string): string {
    const t =
      topico ??
      (typeof mensagem === "object" && mensagem !== null && !Array.isArray(mensagem)
        ? (mensagem as any).schema
        : undefined);
    const erros = typeof t === "string" ? this.validar(t, mensagem) : ["(raiz): mensagem sem o campo 'schema'"];
    if (erros.length > 0) throw new ContractError(typeof t === "string" ? t : null, erros);
    return t as string;
  }
}

export type Enviar = (topico: string, dados: Buffer) => unknown | Promise<unknown>;


export async function publish(
  enviar: Enviar,
  validador: Validator,
  mensagem: unknown,
  topico?: string,
): Promise<string> {
  const t = validador.validate(mensagem, topico);
  await enviar(t, Buffer.from(JSON.stringify(mensagem), "utf8"));
  return t;
}
