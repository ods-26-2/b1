# ods-validator (Python)

Biblioteca para validar mensagens do barramento ODS conforme os contratos definidos nos JSON Schemas da Especificação 1.0.

A validação permite identificar mensagens inválidas antes de seu envio ao Kafka, garantindo que os dados estejam de acordo com o contrato esperado pelos componentes.

Os JSON Schemas são **incorporados ao pacote**, portanto não é necessário clonar o repositório, baixar os schemas separadamente ou configurar variáveis de ambiente.

## Instalação

```bash
pip install ods-validator
```

**Requisitos:** Python 3.10 ou superior.

Recomenda-se fixar a versão da biblioteca nas dependências do componente:

```txt
ods-validator==0.1.0
```

A versão do pacote identifica a versão do contrato utilizada na validação.

## Utilização

### Inicialização

```python
from ods_validator import Validator, publish, ContractError

val = Validator()
```

### Validar uma mensagem

A biblioteca disponibiliza diferentes métodos de validação:

```python
# Valida uma mensagem a partir do tópico
errors = val.find_errors("ods.p7.move.command", msg)

# Identifica o tópico pelo campo "schema" da mensagem
message_errors = val.find_message_errors(msg)

# Valida a mensagem e lança ContractError caso seja inválida
try:
    val.validate(msg)
except ContractError as error:
    print("Mensagem inválida:", error.errors)
```

Os métodos `find_errors` e `find_message_errors` retornam uma lista de erros. Uma lista vazia indica que a mensagem é válida.

O método `validate` lança uma exceção `ContractError` quando a mensagem não atende ao contrato. O campo `errors` contém os erros encontrados durante a validação.

### Integrar a validação ao envio para o Kafka

Se o componente já realiza o envio diretamente ao Kafka, basta validar a mensagem antes da publicação:

```python
val.validate(msg)

producer.send("ods.p7.move.command", payload_bytes)
```

Dessa forma, mensagens inválidas são barradas antes de serem enviadas ao Kafka, sem exigir alterações adicionais na lógica de publicação existente.

Também é possível utilizar a função `publish`, que realiza a validação antes de chamar a função responsável pelo envio:

```python
# kafka-python
publish(lambda topic, data: producer.send(topic, data), val, msg)

# confluent-kafka
publish(lambda topic, data: producer.produce(topic, data), val, msg)
```

A função aceita qualquer operação de envio com os argumentos `send(topic, bytes)`, síncrona ou assíncrona. Caso a mensagem seja inválida, a publicação é interrompida e uma exceção `ContractError` é lançada. O envio não é executado.

### Interface de linha de comando

A biblioteca também disponibiliza o comando `ods-validate` para validar mensagens diretamente pelo terminal.

```bash
# Validar um arquivo JSON
ods-validate mensagem.json

# Validar uma mensagem recebida pela entrada padrão
cat mensagem.json | ods-validate --topic ods.p4.frame -

# Consultar a origem e as informações dos schemas
ods-validate --info
```

O comando retorna código de saída `0` quando a mensagem é válida e `1` quando é inválida.

## Compatibilidade entre as bibliotecas

As bibliotecas Python, TypeScript e C++ utilizam os mesmos JSON Schemas como referência para a validação das mensagens.

Os exemplos compartilhados entre as implementações são utilizados para verificar a consistência dos resultados, garantindo que as três bibliotecas concordem quanto à aceitação ou rejeição das mensagens.

## Limitações

- A validação considera uma mensagem individualmente. Regras que dependem da relação entre mensagens, como correspondência de `correlation_id` entre requisições e respostas ou continuidade de `sequence`, não são verificadas.
- Schemas que não definem `additionalProperties: false` permitem campos adicionais na mensagem.
- O conteúdo e as regras de validação correspondem à versão dos schemas incorporada à versão instalada da biblioteca.

## Repositório

Código-fonte, documentação e especificações dos contratos:

[ods-26-2/b1](https://github.com/ods-26-2/b1)