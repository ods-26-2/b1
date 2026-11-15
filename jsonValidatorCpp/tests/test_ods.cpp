// Roda os mesmos examples/*.json que as bibliotecas Python e TypeScript rodam,
// mais os casos próprios da biblioteca C++. Sem framework: sai com 1 se algo falhar.
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

#include "ods/validator.hpp"

namespace fs = std::filesystem;
using nlohmann::json;

static int g_falhas = 0;
static int g_checagens = 0;

#define CHECK(cond, msg)                                              \
  do {                                                                \
    ++g_checagens;                                                    \
    if (!(cond)) {                                                    \
      ++g_falhas;                                                     \
      std::cerr << "FALHOU: " << (msg) << "  [" #cond "]\n";          \
    }                                                                 \
  } while (0)

static json ler_json(const fs::path& p) {
  std::ifstream in(p, std::ios::binary);
  std::ostringstream ss;
  ss << in.rdbuf();
  return json::parse(ss.str());
}

static json exemplo(const std::string& topico) {
  return ler_json(fs::path(ODS_EXAMPLES_DIR) / (topico + ".json"))["valid"][0];
}

static std::string erros_str(const std::vector<std::string>& v) {
  std::string s;
  for (const auto& e : v) s += e + " | ";
  return s;
}

int main() {
  // sem variável de ambiente, para testar a cópia embutida
  unsetenv(ods::kEnvPasta);
  ods::Validator val;

  // --- carga
  CHECK(val.origem() == "pacote", "origem deve ser 'pacote'");
  CHECK(val.topicos().size() == 56, "esperava 56 tópicos, veio " + std::to_string(val.topicos().size()));
  CHECK(val.schemas_version()["quantidade"] == 56, "quantidade em schemas_version");
  CHECK(val.schemas_version().contains("gerado_em"), "schemas_version tem gerado_em");

  // --- exemplos compartilhados
  std::vector<fs::path> arquivos;
  for (const auto& e : fs::directory_iterator(ODS_EXAMPLES_DIR))
    if (e.path().extension() == ".json") arquivos.push_back(e.path());
  std::sort(arquivos.begin(), arquivos.end());
  CHECK(arquivos.size() == val.topicos().size(), "todo tópico tem arquivo de exemplos");

  size_t validos = 0, invalidos = 0;
  for (const auto& arq : arquivos) {
    const json doc = ler_json(arq);
    const std::string topico = doc["topic"];
    for (const auto& msg : doc["valid"]) {
      ++validos;
      const auto erros = val.validar(topico, msg);
      CHECK(erros.empty(), topico + ": válido foi recusado: " + erros_str(erros));
    }
    for (const auto& c : doc["invalid"]) {
      ++invalidos;
      CHECK(!val.validar(topico, c["message"]).empty(),
            topico + ": inválido '" + c["caso"].get<std::string>() + "' foi aceito");
    }
  }
  std::cout << arquivos.size() << " arquivos, " << validos << " válidos, " << invalidos
            << " inválidos conferidos\n";

  // --- casos próprios
  CHECK(val.validar("ods.nao.existe", json::object())[0].find("desconhecido") != std::string::npos,
        "tópico desconhecido");
  CHECK(!val.validar_mensagem(json{{"producer", "x"}}).empty(), "mensagem sem schema");
  CHECK(!val.validar_mensagem(json::array()).empty(), "raiz array");

  // Sem o verificador de formato, estes dois passariam em silêncio.
  {
    json reply = exemplo("ods.p7.move.reply");
    reply["correlation_id"] = "isto-nao-e-uuid";
    CHECK(!val.validar("ods.p7.move.reply", reply).empty(), "uuid inválido deve falhar");
    json frame = exemplo("ods.p4.frame");
    frame["captured_at"] = "ontem às 10h";
    CHECK(!val.validar("ods.p4.frame", frame).empty(), "date-time inválido deve falhar");
  }

  // O erro aponta o caminho do campo.
  {
    json m = exemplo("ods.p7.move.command");
    m["payload"]["pan_deg"] = 120;
    const auto erros = val.validar("ods.p7.move.command", m);
    bool achou = false;
    for (const auto& e : erros) achou = achou || e.rfind("payload/pan_deg:", 0) == 0;
    CHECK(achou, "erro deve começar com payload/pan_deg: -> " + erros_str(erros));
  }

  // validate lança ContractError
  {
    json m = exemplo("ods.p7.move.command");
    CHECK(val.validate(m) == "ods.p7.move.command", "validate devolve o tópico");
    m["payload"]["pan_deg"] = 500;
    bool lancou = false;
    try {
      val.validate(m);
    } catch (const ods::ContractError& e) {
      lancou = !e.erros().empty() && e.topico() == "ods.p7.move.command";
    }
    CHECK(lancou, "validate deve lançar ContractError");
  }

  // publish valida antes de enviar
  {
    std::vector<std::pair<std::string, std::string>> enviados;
    auto enviar = [&](const std::string& t, const std::string& b) { enviados.push_back({t, b}); };
    json ok = exemplo("ods.p7.move.command");
    ods::publish(enviar, val, ok);
    CHECK(enviados.size() == 1 && enviados[0].first == "ods.p7.move.command", "publish enviou a válida");
    json ruim = ok;
    ruim["payload"]["pan_deg"] = 500;
    bool lancou = false;
    try {
      ods::publish(enviar, val, ruim);
    } catch (const ods::ContractError&) {
      lancou = true;
    }
    CHECK(lancou && enviados.size() == 1, "a inválida não foi enviada");
  }

  // pasta explícita vence o embutido; pasta vazia dá erro claro
  {
    ods::Validator v2(ODS_SCHEMAS_DIR_PATH);
    CHECK(v2.origem() == "argumento", "argumento vence o embutido");
    CHECK(v2.topicos() == val.topicos(), "pasta e embutido têm os mesmos tópicos");

    const fs::path vazia = fs::temp_directory_path() / "ods_vazia_cpp";
    fs::remove_all(vazia);
    fs::create_directories(vazia);
    bool lancou = false;
    try {
      ods::Validator v3(vazia.string());
    } catch (const std::runtime_error& e) {
      lancou = std::string(e.what()).find("nenhum") != std::string::npos;
    }
    CHECK(lancou, "pasta sem schemas dá erro claro");
  }

  // variável de ambiente vence o embutido
  {
    setenv(ods::kEnvPasta, ODS_SCHEMAS_DIR_PATH, 1);
    ods::Validator v4;
    CHECK(v4.origem() == "ODS_SCHEMAS_DIR", "variável vence o embutido");
    unsetenv(ods::kEnvPasta);
  }

  // palavra só do 2020-12 é recusada na carga (o C++ implementa draft-07)
  {
    const fs::path dir = fs::temp_directory_path() / "ods_2020_cpp";
    fs::remove_all(dir);
    fs::create_directories(dir);
    std::ofstream(dir / "x.schema.json")
        << R"({"type":"object","properties":{"schema":{"const":"ods.x.y"},)"
           R"("l":{"type":"array","prefixItems":[{"type":"string"}]}}})";
    bool lancou = false;
    try {
      ods::Validator v5(dir.string());
    } catch (const std::runtime_error& e) {
      lancou = std::string(e.what()).find("prefixItems") != std::string::npos;
    }
    CHECK(lancou, "prefixItems deve ser recusado na carga");
  }

  std::cout << g_checagens << " checagens, " << g_falhas << " falhas\n";
  return g_falhas == 0 ? 0 : 1;
}
