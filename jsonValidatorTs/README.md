# ods-validador (TypeScript)

Valida mensagens do barramento contra os JSON Schemas da Especificação 1.0
(pasta `schemas/` deste repositório). A mensagem fora do contrato é barrada
**antes** de chegar ao Kafka. Mesma API da biblioteca Python.

Os schemas vão **dentro do pacote**: quem instala não precisa clonar nada nem
definir variável de ambiente.

## Instalar

Gere o pacote uma vez, de dentro do clone do `b1`, e entregue o `.tgz`:

```bash
cd b1/jsonValidatorTs
npm install
npm run pack                      # -> ods-validador-0.1.0.tgz
```

Nos componentes:

```bash
npm install ./ods-validador-0.1.0.tgz
```

Requer Node 18 ou mais novo. Mudou um schema? Gere um `.tgz` novo; a versão do
contrato de cada componente é a do pacote instalado.

## Usar

```ts
import { Validator, publish, ContractError } from "ods-validador";

const val = new Validator();                        // usa os schemas do pacote
val.validar("ods.p7.move.command", msg);            // [] se válida, senão lista de erros
val.validarMensagem(msg);                           // descobre o tópico pelo campo "schema"
val.validate(msg);                                  // lança ContractError se inválida
val.schemasVersion;                                 // origem, commit do b1, quantidade
```

### Sem mudar o jeito de publicar

Quem já publica direto no Kafka só acrescenta uma linha antes do envio:

```ts
val.validate(msg);                                  // barra a mensagem fora do contrato
await producer.send({ topic: "ods.p7.move.command", messages: [{ value: JSON.stringify(msg) }] });
```

### Ou publicar já com validação

`publish` aceita qualquer função `enviar(topico, bytes)`, síncrona ou `async`:

```ts
await publish(
  (topico, bytes) => producer.send({ topic: topico, messages: [{ value: bytes }] }),  // kafkajs
  val,
  msg,
);
```

Mensagem inválida rejeita com `ContractError` (campo `.erros`) e nada é enviado.

### Linha de comando

```bash
npx ods-validar mensagem.json             # exit 0 = válida, 1 = inválida
npx ods-validar --topico ods.p4.frame -   # lê da entrada padrão
npx ods-validar --info                    # de onde vêm os schemas
```

## Onde os schemas são procurados

Nesta ordem: opção `new Validator({ dir: "pasta" })`; variável `ODS_SCHEMAS_DIR`;
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
