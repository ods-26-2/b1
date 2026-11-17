# ods-validator (C++)

Valida mensagens do barramento contra os JSON Schemas da Especificação 1.0
(pasta `schemas/` do repositório [ods-26-2/b1](https://github.com/ods-26-2/b1)). A mensagem fora do contrato é barrada
**antes** de chegar ao Kafka. Mesma API das bibliotecas Python e TypeScript.

Requer C++17 e CMake 3.16 ou mais novo.

## Instalar no seu componente

Não há registro de pacotes para C++: o CMake baixa a biblioteca do GitHub, numa
versão fixa (tag), e a compila junto com o seu componente. O build precisa só de
`cmake` e de um compilador, sem `git`.

```cmake
include(FetchContent)
FetchContent_Declare(ods
  URL https://github.com/ods-26-2/b1/archive/refs/tags/v0.1.0.tar.gz
  SOURCE_SUBDIR jsonValidatorCpp)
FetchContent_MakeAvailable(ods)
target_link_libraries(my_component PRIVATE ods::validator)
```

Troque `v0.1.0` pela versão do contrato que o componente usa. Já tem o clone do
`b1`? `add_subdirectory(caminho/para/b1/jsonValidatorCpp ods)` faz o mesmo.

Os schemas embutidos são os do arquivo da tag (ou de `../schemas` no clone). Para
outra pasta: `-DODS_SCHEMAS_DIR=/caminho`. As dependências
([nlohmann/json](https://github.com/nlohmann/json) 3.11.3 e
[json-schema-validator](https://github.com/pboettch/json-schema-validator) 2.3.0)
também são baixadas como arquivos; se estiverem instaladas no sistema, o
`CMakeLists.txt` as usa (`find_package`) em vez de baixar.

Testei o consumo com um arquivo local equivalente ao que o GitHub gera para uma
tag, inclusive num ambiente sem `git`. O endereço acima passa a funcionar quando
a tag existir. Sem internet (por exemplo, uma Jetson offline), instale as duas
dependências no sistema; esse caminho ainda precisa ser conferido numa Jetson.

## Usar

```cpp
#include <ods/validator.hpp>

ods::Validator val;                                // usa os schemas embutidos
val.find_errors("ods.p7.move.command", msg);       // vector<string>; vazio = válida
val.find_message_errors(msg);                     // descobre o tópico pelo campo "schema"
val.validate(msg);                                 // lança ods::ContractError se inválida
val.schemas_version();                             // origin, commit do b1, count
```

`msg` é um `nlohmann::json`.

### Sem mudar o jeito de publicar

Quem já publica direto no Kafka só acrescenta uma linha antes do envio:

```cpp
val.validate(msg);                                 // barra a mensagem fora do contrato
producer.send("ods.p7.move.command", msg.dump());     // como já era
```

### Ou publicar já com validação

`publish` aceita qualquer função `send(topic, bytes)`:

```cpp
ods::publish([&](const std::string& t, const std::string& b) { producer.send(t, b); },
             val, msg);
```

Mensagem inválida lança `ods::ContractError` (método `errors()`) e nada é enviado.

### Linha de comando

```bash
ods-validate mensagem.json             # exit 0 = válida, 1 = inválida
ods-validate --topic ods.p4.frame -   # lê da entrada padrão
ods-validate --info                    # de onde vêm os schemas
```

## Onde os schemas são procurados

Nesta ordem: argumento `ods::Validator("caminho/dos/schemas")`; variável `ODS_SCHEMAS_DIR`;
cópia embutida. Os dois primeiros servem para testar um schema ainda não
publicado. O tópico é o `properties.schema.const` de cada schema; só
`*.schema.json` é lido.

## Compilar e testar

```bash
cd jsonValidatorCpp
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build --output-on-failure
```

O teste roda os mesmos `examples/*.json` que as bibliotecas Python e
TypeScript (todo válido precisa passar, todo inválido precisa falhar) e
confere que `uuid` e `date-time` são checados de verdade.

## Detalhes de implementação

- **A biblioteca de validação em C++ implementa o JSON Schema draft-07**,
  enquanto os schemas declaram 2020-12. Hoje funciona porque os schemas só
  usam palavras que existem nos dois (`type`, `required`, `properties`,
  `const`, `enum`, `if/then`, `allOf`, `oneOf`, `anyOf`, `pattern`, limites e
  `format`). Se alguém passar a usar uma palavra só do 2020-12
  (`prefixItems`, `$defs`, `unevaluatedProperties` etc.), a carga falha com o
  nome do arquivo e da palavra, em vez de o C++ ignorá-la e divergir.
- `format` só vale com um verificador explícito, que a biblioteca passa:
  `date-time`, `date`, `time`, `uri`, `email`, `ipv4`, `ipv6`, `uuid` e
  `hostname`. Outros formatos são ignorados, como no Python.
- O texto das mensagens de erro difere entre as linguagens. O que vale como
  contrato é aceitar ou recusar a mensagem, e os `examples/` garantem que as
  três concordam.
- Não testei o uso do mesmo `Validator` por várias threads ao mesmo tempo;
  se precisar, crie um por thread ou valide antes.

## Limites conhecidos

- Valida **uma** mensagem.
- Schemas sem `additionalProperties: false` aceitam campos desconhecidos.
- Só há build com CMake; não gera pacote instalável (`install`/`find_package`).
