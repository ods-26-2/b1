## Instalar

```bash
git clone https://github.com/ods-26-2/b1.git          # os schemas
pip install ./ods_validador                           # esta biblioteca
export ODS_SCHEMAS_DIR=$PWD/b1                        # onde estão os schemas
```

## Usar

```python
from ods_validador import Validador, publicar, ErroDeContrato

val = Validador()                      # lê ODS_SCHEMAS_DIR
val.validar("ods.p7.move.command", msg)   # -> [] se válida, senão lista de erros
val.validar_mensagem(msg)                 # descobre o tópico pelo campo "schema"
```

O tópico é o valor de `properties.schema.const` de cada schema; nome de arquivo
e pasta não entram na busca.

### Publicar com validação

`publicar` aceita qualquer função `enviar(topico, bytes)`.

```python
# kafka-python
from kafka import KafkaProducer
p = KafkaProducer(bootstrap_servers="HOST:PORTA")
publicar(lambda t, b: p.send(t, b), val, msg)

# confluent-kafka
from confluent_kafka import Producer
p = Producer({"bootstrap.servers": "HOST:PORTA"})
publicar(lambda t, b: p.produce(t, b), val, msg)
```

Mensagem inválida levanta `ErroDeContrato` (com `.erros`) e nada é enviado.
