# ods-validator

Valida mensagens do barramento contra os JSON Schemas da Especificação 1.0
(repositório [ods-26-2/b1](https://github.com/ods-26-2/b1)). Entregável B1 da TRA-1: a mensagem fora do contrato
é barrada **antes** de chegar ao Kafka.

Os schemas vão **dentro do pacote**: quem instala não precisa clonar nada
nem definir variável de ambiente.

## Instalar

```bash
pip install ods-validator
```

Os schemas vêm dentro do pacote. Fixe a versão nos componentes
(`ods-validator==0.1.0`): a versão do pacote é a versão do contrato.

Para desenvolver a biblioteca, a partir do clone do `b1`:

```bash
pip install -e "./jsonValidatorPy[dev]"
```

## Usar

```python
from ods_validator import Validator, publish, ContractError

val = Validator()                         # usa os schemas do pacote
val.find_errors("ods.p7.move.command", msg)   # [] se válida, senão lista de erros
val.find_message_errors(msg)                 # descobre o tópico pelo campo "schema"
val.validate(msg)                         # levanta ContractError se inválida
val.schemas_version                       # origin, commit do b1, count
```

### Sem mudar o jeito de publicar

Quem já publica direto no Kafka só acrescenta uma linha antes do envio:

```python
val.validate(msg)                      # barra a mensagem fora do contrato
producer.send("ods.p7.move.command", payload_bytes)   # como já era
```

### Ou publicar já com validação

`publish` aceita qualquer função `send(topic, bytes)`.

```python
publish(lambda t, b: producer.send(t, b), val, msg)      # kafka-python
publish(lambda t, b: producer.produce(t, b), val, msg)   # confluent-kafka
```

Mensagem inválida levanta `ContractError` (com `.errors`) e nada é enviado.

### Linha de comando

```bash
ods-validate mensagem.json             # exit 0 = válida, 1 = inválida
ods-validate --topic ods.p4.frame -   # lê da entrada padrão
ods-validate --info                    # de onde vêm os schemas
```

## Onde os schemas são procurados

Nesta ordem: argumento `Validator("caminho/dos/schemas")`; variável `ODS_SCHEMAS_DIR`;
a pasta `schemas/` do clone do `b1` (quando o código roda de dentro dele, como
na instalação editável); cópia embutida no pacote (quem instalou o wheel). Os
dois primeiros servem para testar um schema ainda não publicado. O tópico é o
`properties.schema.const` de cada schema; nome de arquivo e pasta não entram
na busca, mas só `*.schema.json` é lido.

## Desenvolvimento e testes

```bash
cd jsonValidatorPy
pip install -e ".[dev]"
pytest
```

Para cada schema o teste gera um exemplo válido, confere que passa, remove
cada campo obrigatório (envelope e payload), troca o tipo e o tópico, e
verifica que falha. Também confere que `uuid` e `date-time` são checados de
verdade (o `jsonschema` ignora `format` por padrão).

## Limites conhecidos

- Valida **uma** mensagem. Regras entre mensagens (`correlation_id` da reply,
  lacuna em `sequence`) ficam para a TRA-2.
- Schemas sem `additionalProperties: false` aceitam campos desconhecidos.
