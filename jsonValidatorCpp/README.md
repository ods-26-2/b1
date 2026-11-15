# ods-validador (C++)

Valida mensagens do barramento contra os JSON Schemas da Especificação 1.0
(pasta `schemas/` deste repositório). A mensagem fora do contrato é barrada
**antes** de chegar ao Kafka. Mesma API das bibliotecas Python e TypeScript.

Os schemas são **embutidos na biblioteca** em tempo de build, em um cabeçalho
gerado. O programa não procura arquivo nenhum em tempo de execução, o que
evita problema de caminho na Jetson.

Requer C++17 e CMake 3.16 ou mais novo. Dependências, baixadas pelo CMake se
não existirem no sistema: [nlohmann/json](https://github.com/nlohmann/json)
3.11.3 e [json-schema-validator](https://github.com/pboettch/json-schema-validator)
2.3.0.

## Usar no seu componente

Com o clone do `b1` ao lado do código do componente:

```cmake
add_subdirectory(caminho/para/b1/jsonValidatorCpp ods)
target_link_libraries(meu_componente PRIVATE ods::validador)
```

Ou, sem clone fixo, pelo `FetchContent`:

```cmake
include(FetchContent)
FetchContent_Declare(ods GIT_REPOSITORY https://github.com/ods-26-2/b1.git
                         GIT_TAG main SOURCE_SUBDIR jsonValidatorCpp)
FetchContent_MakeAvailable(ods)
target_link_libraries(meu_componente PRIVATE ods::validador)
```

(Testei o `add_subdirectory`; o `FetchContent` usa o mesmo `CMakeLists.txt`,
mas não o testei contra o GitHub porque estas alterações ainda não estão lá.)

Os schemas embutidos são os de `../schemas` do clone no momento do build. Para
outra pasta: `-DODS_SCHEMAS_DIR=/caminho`. Offline (Jetson sem internet),
instale `nlohmann_json` e `nlohmann_json_schema_validator` no sistema: o
`CMakeLists.txt` tenta `find_package` antes de baixar. Só testei o caminho
com download; o caminho offline ainda precisa ser conferido numa Jetson.

```cpp
#include <ods/validator.hpp>

ods::Validator val;                                // usa os schemas embutidos
val.validar("ods.p7.move.command", msg);           // vector<string>; vazio = válida
val.validar_mensagem(msg);                         // descobre o tópico pelo campo "schema"
val.validate(msg);                                 // lança ods::ContractError se inválida
val.schemas_version();                             // origem, commit do b1, quantidade
```

`msg` é um `nlohmann::json`.

### Sem mudar o jeito de publicar

Quem já publica direto no Kafka só acrescenta uma linha antes do envio:

```cpp
val.validate(msg);                                 // barra a mensagem fora do contrato
produtor.enviar("ods.p7.move.command", msg.dump());   // como já era
```

### Ou publicar já com validação

`publish` aceita qualquer função `enviar(topico, bytes)`:

```cpp
ods::publish([&](const std::string& t, const std::string& b) { produtor.enviar(t, b); },
             val, msg);
```

Mensagem inválida lança `ods::ContractError` (método `erros()`) e nada é enviado.

### Linha de comando

```bash
ods-validar mensagem.json             # exit 0 = válida, 1 = inválida
ods-validar --topico ods.p4.frame -   # lê da entrada padrão
ods-validar --info                    # de onde vêm os schemas
```

## Onde os schemas são procurados

Nesta ordem: argumento `ods::Validator("pasta")`; variável `ODS_SCHEMAS_DIR`;
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

- Valida **uma** mensagem. Regras entre mensagens (`correlation_id` da reply,
  lacuna em `sequence`) ficam para a TRA-2.
- Schemas sem `additionalProperties: false` aceitam campos desconhecidos.
- Só há build com CMake; não gera pacote instalável (`install`/`find_package`).
