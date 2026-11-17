# ods-validator (TypeScript)

Valida mensagens do barramento contra os JSON Schemas da Especificação 1.0
(pasta `schemas/` do repositório [ods-26-2/b1](https://github.com/ods-26-2/b1)). A mensagem fora do contrato é barrada
**antes** de chegar ao Kafka. Mesma API da biblioteca Python.

Os schemas vão **dentro do pacote**: quem instala não precisa clonar nada nem
definir variável de ambiente.

## Instalar

```bash
npm install ods-validator
```

Requer Node 18 ou mais novo. Os schemas vêm dentro do pacote. Fixe a versão
nos componentes (`"ods-validator": "0.1.0"`): a versão do pacote é a versão do
contrato.

Para desenvolver a biblioteca, a partir do clone do `b1`:

```bash
cd jsonValidatorTs && npm install && npm test
```

## Usar

```ts
import { Validator, publish, ContractError } from "ods-validator";

const val = new Validator();                        // usa os schemas do pacote
val.findErrors("ods.p7.move.command", msg);          // [] se válida, senão lista de erros
val.findMessageErrors(msg);                         // descobre o tópico pelo campo "schema"
val.validate(msg);                                  // lança ContractError se inválida
val.schemasVersion;                                 // origin, commit do b1, count
```

### Sem mudar o jeito de publicar

Quem já publica direto no Kafka só acrescenta uma linha antes do envio:

```ts
val.validate(msg);                                  // barra a mensagem fora do contrato
await producer.send({ topic: "ods.p7.move.command", messages: [{ value: JSON.stringify(msg) }] });
```

### Ou publicar já com validação

`publish` aceita qualquer função `send(topic, bytes)`, síncrona ou `async`:

```ts
await publish(
  (topic, bytes) => producer.send({ topic, messages: [{ value: bytes }] }),  // kafkajs
  val,
  msg,
);
```

Mensagem inválida rejeita com `ContractError` (campo `.errors`) e nada é enviado.

### Linha de comando

```bash
npx ods-validate mensagem.json             # exit 0 = válida, 1 = inválida
npx ods-validate --topic ods.p4.frame -   # lê da entrada padrão
npx ods-validate --info                    # de onde vêm os schemas
```

## Onde os schemas são procurados

Nesta ordem: opção `new Validator({ dir: "caminho/dos/schemas" })`; variável `ODS_SCHEMAS_DIR`;
cópia embutida no pacote. Os dois primeiros servem para testar um schema ainda
não publicado. O tópico é o `properties.schema.const` de cada schema; só
`*.schema.json` é lido.

## Desenvolvimento e testes

```bash
cd jsonValidatorTs
npm install
npm test          # gera os schemas embutidos, compila e roda os testes
```

O teste roda os mesmos `examples/*.json` que as bibliotecas Python e C++
(todo válido precisa passar, todo inválido precisa falhar) e confere que
`uuid` e `date-time` são checados de verdade.

## Detalhes de implementação

- Usa Ajv (draft 2020-12) com `ajv-formats`. O modo estrito fica ligado, de
  modo que uma palavra desconhecida num schema falha na carga. Ficam
  desligados só `strictTypes` e `strictRequired`: os schemas usam `type` em
  lista e `then.required` de campos definidos no nível acima, que são JSON
  Schema válido.
- O texto das mensagens de erro difere entre as linguagens (cada uma usa a
  sua biblioteca). O que vale como contrato é aceitar ou recusar a mensagem,
  e os `examples/` garantem que as três concordam.
- `src/generated/` é gerado no build a partir de `../schemas` e não vai ao git.

## Limites conhecidos

- Valida **uma** mensagem. Regras entre mensagens (`correlation_id` da reply,
  lacuna em `sequence`) ficam para a TRA-2.
- Schemas sem `additionalProperties: false` aceitam campos desconhecidos.
