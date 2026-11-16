# b1 — contratos do barramento (Especificação de interfaces 1.0)

```
schemas/            os contratos: um JSON Schema por mensagem (B5/, I1/, ... S6/)
examples/           um arquivo por tópico com mensagens válidas e inválidas (GERADO)
tools/              generate_examples.py: gera examples/ a partir dos schemas
jsonValidatorPy/    biblioteca Python
jsonValidatorTs/    biblioteca TypeScript
jsonValidatorCpp/   biblioteca C++
```

As três bibliotecas têm a mesma API e fazem a mesma coisa: validam uma
mensagem contra o schema do seu tópico **antes** de ela ir para o Kafka. Cada
uma leva os schemas embutidos, então quem instala não precisa clonar este
repositório.

## Como as três ficam iguais

O que vale como contrato é aceitar ou recusar a mensagem. As bibliotecas usam
motores diferentes, e o texto dos erros muda de uma para outra. Para que não
divirjam, as três rodam os mesmos `examples/*.json` nos testes: todo exemplo
`valid` precisa passar e todo `invalid` precisa falhar.

## Mudou um schema?

```bash
python tools/generate_examples.py      # regera examples/ (rode com a lib Python instalada)
(cd jsonValidatorPy  && pip install -e ".[dev]" && pytest)
(cd jsonValidatorTs  && npm install && npm test)
(cd jsonValidatorCpp && cmake -S . -B build && cmake --build build -j && ctest --test-dir build)
```

Depois gere de novo o pacote de cada linguagem (wheel, `.tgz`) e redistribua:
a versão do contrato que um componente usa é a do pacote que ele instalou.
Os `examples/` são gerados: não edite à mão.

Cada biblioteca tem o seu README com a instalação e o uso.
