#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>

#include "ods/validator.hpp"

namespace fs = std::filesystem;
using nlohmann::json;

static int g_failures = 0;
static int g_checks = 0;

#define CHECK(cond, msg)                                     \
  do {                                                       \
    ++g_checks;                                              \
    if (!(cond)) {                                           \
      ++g_failures;                                          \
      std::cerr << "FALHOU: " << (msg) << "  [" #cond "]\n"; \
    }                                                        \
  } while (0)

static json read_json(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  std::ostringstream ss;
  ss << in.rdbuf();
  return json::parse(ss.str());
}

static json example(const std::string& topic) {
  return read_json(fs::path(ODS_EXAMPLES_DIR) / (topic + ".json"))["valid"][0];
}

static std::string join_errors(const std::vector<std::string>& errors) {
  std::string text;
  for (const auto& e : errors) text += e + " | ";
  return text;
}

int main() {
  // sem variável de ambiente, para exercitar os schemas embutidos
  unsetenv(ods::kEnvSchemasDir);
  ods::Validator validator;

  CHECK(validator.origin() == "package", "origin deve ser 'package'");
  CHECK(validator.topics().size() == 56, "esperava 56 tópicos, veio " + std::to_string(validator.topics().size()));
  CHECK(validator.schemas_version()["count"] == 56, "count em schemas_version");
  CHECK(validator.schemas_version().contains("generated_at"), "schemas_version tem generated_at");

  std::vector<fs::path> files;
  for (const auto& entry : fs::directory_iterator(ODS_EXAMPLES_DIR))
    if (entry.path().extension() == ".json") files.push_back(entry.path());
  std::sort(files.begin(), files.end());
  CHECK(files.size() == validator.topics().size(), "todo tópico tem arquivo de exemplos");

  size_t valid_count = 0, invalid_count = 0;
  for (const auto& file : files) {
    const json doc = read_json(file);
    const std::string topic = doc["topic"];
    for (const auto& message : doc["valid"]) {
      ++valid_count;
      const auto errors = validator.find_errors(topic, message);
      CHECK(errors.empty(), topic + ": válido foi recusado: " + join_errors(errors));
    }
    for (const auto& c : doc["invalid"]) {
      ++invalid_count;
      CHECK(!validator.find_errors(topic, c["message"]).empty(),
            topic + ": inválido '" + c["case"].get<std::string>() + "' foi aceito");
    }
  }
  std::cout << files.size() << " arquivos, " << valid_count << " válidos, " << invalid_count
            << " inválidos conferidos\n";

  CHECK(validator.find_errors("ods.nao.existe", json::object())[0].find("desconhecido") != std::string::npos,
        "tópico desconhecido");
  CHECK(!validator.find_message_errors(json{{"producer", "x"}}).empty(), "mensagem sem schema");
  CHECK(!validator.find_message_errors(json::array()).empty(), "raiz array");

  // sem o verificador de formato, estes dois passariam em silêncio
  {
    json reply = example("ods.p7.move.reply");
    reply["correlation_id"] = "isto-nao-e-uuid";
    CHECK(!validator.find_errors("ods.p7.move.reply", reply).empty(), "uuid inválido deve falhar");
    json frame = example("ods.p4.frame");
    frame["captured_at"] = "ontem às 10h";
    CHECK(!validator.find_errors("ods.p4.frame", frame).empty(), "date-time inválido deve falhar");
  }

  {
    json message = example("ods.p7.move.command");
    message["payload"]["pan_deg"] = 120;
    const auto errors = validator.find_errors("ods.p7.move.command", message);
    bool found = false;
    for (const auto& e : errors) found = found || e.rfind("payload/pan_deg:", 0) == 0;
    CHECK(found, "erro deve começar com payload/pan_deg: -> " + join_errors(errors));
  }

  {
    json message = example("ods.p7.move.command");
    CHECK(validator.validate(message) == "ods.p7.move.command", "validate devolve o tópico");
    message["payload"]["pan_deg"] = 500;
    bool thrown = false;
    try {
      validator.validate(message);
    } catch (const ods::ContractError& e) {
      thrown = !e.errors().empty() && e.topic() == "ods.p7.move.command";
    }
    CHECK(thrown, "validate deve lançar ContractError");
  }

  {
    std::vector<std::pair<std::string, std::string>> sent;
    auto send = [&](const std::string& t, const std::string& b) { sent.push_back({t, b}); };
    json valid = example("ods.p7.move.command");
    ods::publish(send, validator, valid);
    CHECK(sent.size() == 1 && sent[0].first == "ods.p7.move.command", "publish enviou a válida");
    json invalid = valid;
    invalid["payload"]["pan_deg"] = 500;
    bool thrown = false;
    try {
      ods::publish(send, validator, invalid);
    } catch (const ods::ContractError&) {
      thrown = true;
    }
    CHECK(thrown && sent.size() == 1, "a inválida não foi enviada");
  }

  {
    ods::Validator from_dir(ODS_SCHEMAS_DIR_PATH);
    CHECK(from_dir.origin() == "argument", "argumento vence o embutido");
    CHECK(from_dir.topics() == validator.topics(), "pasta e embutido têm os mesmos tópicos");

    const fs::path empty = fs::temp_directory_path() / "ods_empty_cpp";
    fs::remove_all(empty);
    fs::create_directories(empty);
    bool thrown = false;
    try {
      ods::Validator none(empty.string());
    } catch (const std::runtime_error& e) {
      thrown = std::string(e.what()).find("nenhum") != std::string::npos;
    }
    CHECK(thrown, "pasta sem schemas dá erro claro");
  }

  {
    setenv(ods::kEnvSchemasDir, ODS_SCHEMAS_DIR_PATH, 1);
    ods::Validator from_env;
    CHECK(from_env.origin() == "ODS_SCHEMAS_DIR", "variável vence o embutido");
    unsetenv(ods::kEnvSchemasDir);
  }

  // palavra só do 2020-12 é recusada na carga
  {
    const fs::path dir = fs::temp_directory_path() / "ods_2020_cpp";
    fs::remove_all(dir);
    fs::create_directories(dir);
    std::ofstream(dir / "x.schema.json")
        << R"({"type":"object","properties":{"schema":{"const":"ods.x.y"},)"
           R"("l":{"type":"array","prefixItems":[{"type":"string"}]}}})";
    bool thrown = false;
    try {
      ods::Validator v(dir.string());
    } catch (const std::runtime_error& e) {
      thrown = std::string(e.what()).find("prefixItems") != std::string::npos;
    }
    CHECK(thrown, "prefixItems deve ser recusado na carga");
  }

  std::cout << g_checks << " checagens, " << g_failures << " falhas\n";
  return g_failures == 0 ? 0 : 1;
}
