# ods-validator (C++)

Biblioteca para validar mensagens do barramento ODS conforme os contratos definidos nos JSON Schemas da Especificação 1.0.

A validação permite identificar mensagens inválidas antes de seu envio ao Kafka, garantindo que os dados estejam de acordo com o contrato esperado pelos componentes.

Os JSON Schemas são **incorporados à biblioteca**, portanto não é necessário baixar ou gerenciar os schemas separadamente.

**Requisitos:** C++17 e CMake 3.16 ou superior.

## Instalação

A biblioteca pode ser incorporada diretamente ao projeto utilizando o CMake e `FetchContent`. Dessa forma, o CMake baixa e compila a biblioteca junto com o componente.

Adicione ao `CMakeLists.txt`:

```cmake
include(FetchContent)

FetchContent_Declare(
    ods
    URL https://github.com/ods-26-2/b1/archive/refs/tags/v0.1.0.tar.gz
    SOURCE_SUBDIR jsonValidatorCpp
)

FetchContent_MakeAvailable(ods)

target_link_libraries(my_component PRIVATE ods::validator)
```

Substitua `v0.1.0` pela versão do contrato utilizada pelo componente.

As dependências necessárias são baixadas automaticamente pelo CMake quando não estão instaladas no sistema.

Caso já possua um clone do repositório, também é possível incorporar a biblioteca diretamente:

```cmake
add_subdirectory(caminho/para/b1/jsonValidatorCpp ods)

target_link_libraries(my_component PRIVATE ods::validator)
```

## Utilização

### Inicialização

```cpp
#include <ods/validator.hpp>

ods::Validator val;
```

Por padrão, a biblioteca utiliza os JSON Schemas incorporados à versão instalada.

As mensagens devem ser representadas utilizando `nlohmann::json`.

### Validar uma mensagem

A biblioteca disponibiliza diferentes métodos de validação:

```cpp
// Valida uma mensagem a partir do tópico
auto errors = val.find_errors("ods.p7.move.command", msg);

// Identifica o tópico pelo campo "schema" da mensagem
auto message_errors = val.find_message_errors(msg);

// Valida a mensagem e lança ods::ContractError caso seja inválida
try {
    val.validate(msg);
} catch (const ods::ContractError& error) {
    for (const auto& detail : error.errors()) {
        std::cerr << detail << std::endl;
    }
}
```

Os métodos `find_errors` e `find_message_errors` retornam um `std::vector<std::string>`. Um vetor vazio indica que a mensagem é válida.

O método `validate` lança uma exceção `ods::ContractError` quando a mensagem não atende ao contrato. O método `errors()` disponibiliza os erros encontrados durante a validação.

### Integrar a validação ao envio para o Kafka

Se o componente já realiza o envio diretamente ao Kafka, basta validar a mensagem antes da publicação:

```cpp
val.validate(msg);

producer.send("ods.p7.move.command", msg.dump());
```

Dessa forma, mensagens inválidas são barradas antes de serem enviadas ao Kafka, sem exigir alterações adicionais na lógica de publicação existente.

Também é possível utilizar a função `ods::publish`, que realiza a validação antes de chamar a função responsável pelo envio:

```cpp
ods::publish(
    [&](const std::string& topic, const std::string& bytes) {
        producer.send(topic, bytes);
    },
    val,
    msg
);
```

A função aceita operações de envio síncronas ou assíncronas, desde que sejam compatíveis com a interface esperada. Caso a mensagem seja inválida, uma exceção `ods::ContractError` é lançada e o envio não é executado.

## Interface de linha de comando

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

Embora utilizem bibliotecas de validação diferentes, as implementações mantêm o mesmo comportamento esperado em relação aos contratos.

## Limitações

- A validação considera uma mensagem individualmente. Regras que dependem da relação entre mensagens, como correspondência de `correlation_id` entre requisições e respostas ou continuidade de `sequence`, não são verificadas.
- Schemas que não definem `additionalProperties: false` permitem campos adicionais na mensagem.
- A biblioteca utiliza uma implementação de JSON Schema draft-07. Os schemas atuais utilizam apenas recursos compatíveis com essa versão, embora declarem 2020-12. O uso de recursos exclusivos de versões posteriores não é suportado.
- O suporte a `format` contempla `date-time`, `date`, `time`, `uri`, `email`, `ipv4`, `ipv6`, `uuid` e `hostname`.
- O uso simultâneo da mesma instância de `Validator` por múltiplas threads não foi testado.

## Repositório

Código-fonte, documentação e especificações dos contratos:

[ods-26-2/b1](https://github.com/ods-26-2/b1)