import copy
import json
import pytest

from ods_validador import ContractError, Validator, publish
from exemplos import gerar, gerar_mensagem

ARQUIVOS = sorted(Validator().pasta.rglob("*.schema.json"))


@pytest.fixture(scope="module")
def val():
    return Validator()


def _carrega(arq):
    return json.loads(arq.read_text(encoding="utf-8"))


@pytest.fixture(params=ARQUIVOS, ids=lambda a: f"{a.parent.name}/{a.stem}")
def caso(request, val):
    schema = _carrega(request.param)
    topico = schema["properties"]["schema"]["const"]
    return topico, schema, gerar_mensagem(schema)


def test_carrega_todos_sem_duplicata(val):
    assert len(val.topicos) == len(ARQUIVOS) > 0


def test_versao_dos_schemas(val):
    info = val.schemas_version
    assert info["quantidade"] == len(ARQUIVOS)
    assert info["origem"] in {"pacote", "repositório", "ODS_SCHEMAS_DIR"}


def test_argumento_vence_variavel_de_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("ODS_SCHEMAS_DIR", str(tmp_path))  # vazia: falharia
    v = Validator(ARQUIVOS[0].parent)
    assert v.origem == "argumento"


def test_variavel_de_ambiente_vence_o_padrao(tmp_path, monkeypatch):
    monkeypatch.setenv("ODS_SCHEMAS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="nenhum"):
        Validator()  # usou a pasta vazia da variável, não a embutida


def test_pasta_sem_schemas_e_erro_claro(tmp_path):
    with pytest.raises(ValueError, match="nenhum"):
        Validator(tmp_path)


def test_exemplo_valido_passa(val, caso):
    topico, _, msg = caso
    assert val.validar(topico, msg) == []


def test_campo_obrigatorio_ausente_falha(val, caso):
    topico, schema, msg = caso
    for campo in schema["required"]:
        ruim = copy.deepcopy(msg)
        del ruim[campo]
        assert val.validar(topico, ruim), f"aceitou sem '{campo}'"


def test_payload_obrigatorio_ausente_falha(val, caso):
    topico, schema, msg = caso
    for campo in schema["properties"]["payload"].get("required", []):
        ruim = copy.deepcopy(msg)
        ruim["payload"].pop(campo, None)
        assert val.validar(topico, ruim), f"aceitou payload sem '{campo}'"


def test_tipo_errado_no_envelope_falha(val, caso):
    topico, _, msg = caso
    ruim = copy.deepcopy(msg)
    ruim["producer"] = 123
    assert val.validar(topico, ruim)


def test_topico_trocado_falha(val, caso):
    topico, _, msg = caso
    outro = next(t for t in val.topicos if t != topico)
    assert val.validar(outro, msg)


def test_mensagem_nao_objeto_falha(val, caso):
    topico, _, _ = caso
    assert val.validar(topico, [])
    assert val.validar(topico, "texto")


def test_topico_desconhecido(val):
    assert "desconhecido" in val.validar("ods.nao.existe", {})[0]


def test_sem_campo_schema(val):
    assert val.validar_mensagem({"producer": "x"})


# --- format: sem FormatChecker estes dois passariam em silêncio ---
def test_uuid_invalido_falha(val):
    msg = {k: v for k, v in gerar_p7_reply(val).items()}
    msg["correlation_id"] = "isto-nao-e-uuid"
    assert val.validar("ods.p7.move.reply", msg)


def test_data_invalida_falha(val):
    msg = gerar_frame(val)
    msg["captured_at"] = "ontem às 10h"
    assert val.validar("ods.p4.frame", msg)


def gerar_p7_reply(val):
    s = _carrega(next(a for a in ARQUIVOS if a.stem == "moveReply.schema"))
    return gerar(s)


def gerar_frame(val):
    s = _carrega(next(a for a in ARQUIVOS if a.stem == "frameEvent.schema"))
    return gerar(s)


# --- regras específicas conhecidas ---
def _move_command(val):
    s = _carrega(next(a for a in ARQUIVOS if a.stem == "moveCommand.schema"))
    return gerar(s)


def test_pan_fora_do_limite_falha(val):
    msg = _move_command(val)
    msg["payload"]["pan_deg"] = 91
    assert val.validar("ods.p7.move.command", msg)


def test_reply_error_exige_bloco_error(val):
    msg = gerar_p7_reply(val)
    msg["payload"] = {"status": "ERROR"}
    assert val.validar("ods.p7.move.reply", msg)
    msg["payload"]["error"] = {"code": "OUT_OF_RANGE", "message": "fora do limite"}
    assert val.validar("ods.p7.move.reply", msg) == []


# --- publicar ---
def test_publicar_valida_antes_de_enviar(val):
    enviados = []
    ok = _move_command(val)
    publish(lambda t, b: enviados.append((t, b)), val, ok)
    assert enviados[0][0] == "ods.p7.move.command"

    ruim = copy.deepcopy(ok)
    ruim["payload"]["pan_deg"] = 500
    with pytest.raises(ContractError) as e:
        publish(lambda t, b: enviados.append((t, b)), val, ruim)
    assert "pan_deg" in str(e.value)
    assert len(enviados) == 1  # a inválida não foi enviada
