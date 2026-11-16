#include "ods/validator.hpp"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>

#include <nlohmann/json-schema.hpp>

#include "ods_schemas.hpp"  // gerado no build por cmake/EmbedSchemas.cmake

namespace fs = std::filesystem;
using nlohmann::json;

namespace ods {

namespace {

const std::string kSuffix = ".schema.json";

// a biblioteca de validação em C++ implementa o draft-07; palavras só do 2020-12
// seriam ignoradas em silêncio, então a carga as recusa
const std::set<std::string>& forbidden_keywords() {
  static const std::set<std::string> keywords{
      "prefixItems",      "unevaluatedProperties", "unevaluatedItems", "dependentRequired",
      "dependentSchemas", "$defs",                 "$dynamicRef",      "$dynamicAnchor",
      "$anchor",          "minContains",           "maxContains",      "contentSchema"};
  return keywords;
}

void check_keywords(const json& schema, const std::string& file) {
  if (!schema.is_object()) return;
  for (const auto& kv : schema.items()) {
    if (forbidden_keywords().count(kv.key())) {
      throw std::runtime_error(file + ": a palavra '" + kv.key() +
                               "' é só do JSON Schema 2020-12 e esta biblioteca C++ "
                               "(draft-07) não a implementa");
    }
  }
  for (const char* key : {"properties", "patternProperties"}) {
    if (schema.contains(key) && schema[key].is_object())
      for (const auto& kv : schema[key].items()) check_keywords(kv.value(), file);
  }
  for (const char* key : {"allOf", "anyOf", "oneOf"}) {
    if (schema.contains(key) && schema[key].is_array())
      for (const auto& sub : schema[key]) check_keywords(sub, file);
  }
  for (const char* key : {"if", "then", "else", "not", "additionalProperties", "contains"}) {
    if (schema.contains(key)) check_keywords(schema[key], file);
  }
  if (schema.contains("items")) {
    if (schema["items"].is_array())
      for (const auto& sub : schema["items"]) check_keywords(sub, file);
    else
      check_keywords(schema["items"], file);
  }
}

// sem um verificador explícito, "format" não é validado; formatos desconhecidos são ignorados
void check_format(const std::string& format, const std::string& value) {
  static const std::set<std::string> known{"date-time", "date", "time", "uri", "email",
                                           "ipv4",      "ipv6", "uuid", "hostname"};
  if (known.count(format)) nlohmann::json_schema::default_string_format_check(format, value);
}

class ErrorCollector : public nlohmann::json_schema::basic_error_handler {
 public:
  void error(const json::json_pointer& ptr, const json& instance,
             const std::string& message) override {
    nlohmann::json_schema::basic_error_handler::error(ptr, instance, message);
    std::string where = ptr.to_string();
    if (!where.empty() && where[0] == '/') where.erase(0, 1);
    if (where.empty()) where = "(raiz)";
    errors.push_back(where + ": " + message);
  }
  std::vector<std::string> errors;
};

struct Item {
  std::string file;
  json schema;
};

std::string read_file(const fs::path& path) {
  std::ifstream in(path, std::ios::binary);
  if (!in) throw std::runtime_error("não consegui abrir " + path.string());
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

bool ends_with(const std::string& text, const std::string& suffix) {
  return text.size() >= suffix.size() &&
         text.compare(text.size() - suffix.size(), std::string::npos, suffix) == 0;
}

}  // namespace

ContractError::ContractError(std::string topic, std::vector<std::string> errors)
    : std::runtime_error([&] {
        std::string text = topic + ": ";
        for (size_t i = 0; i < errors.size(); ++i) text += (i ? "; " : "") + errors[i];
        return text;
      }()),
      topic_(std::move(topic)),
      errors_(std::move(errors)) {}

struct Validator::Impl {
  std::string origin;
  std::string directory;
  json meta = json::object();
  std::map<std::string, std::shared_ptr<nlohmann::json_schema::json_validator>> by_topic;
  std::map<std::string, std::string> file_of;
};

Validator::Validator(const std::string& directory_arg) {
  auto impl = std::make_shared<Impl>();
  std::vector<Item> items;

  std::string dir = directory_arg;
  if (!dir.empty()) {
    impl->origin = "argument";
  } else if (const char* env = std::getenv(kEnvSchemasDir); env && *env) {
    dir = env;
    impl->origin = kEnvSchemasDir;
  }

  if (!dir.empty()) {
    impl->directory = dir;
    std::vector<fs::path> found;
    for (const auto& entry : fs::recursive_directory_iterator(dir)) {
      if (entry.is_regular_file() && ends_with(entry.path().filename().string(), kSuffix))
        found.push_back(entry.path());
    }
    std::sort(found.begin(), found.end());
    for (const auto& path : found) {
      try {
        items.push_back({fs::relative(path, dir).generic_string(), json::parse(read_file(path))});
      } catch (const json::exception& ex) {
        throw std::runtime_error(path.string() + ": JSON inválido (" + ex.what() + ")");
      }
    }
    const fs::path meta = fs::path(dir) / "VERSION.json";
    if (fs::exists(meta)) impl->meta = json::parse(read_file(meta));
  } else {
    impl->origin = "package";
    for (const auto& item : embedded::kSchemas)
      items.push_back({item.file, json::parse(item.json)});
    impl->meta = {{"commit", embedded::kCommit},
                  {"description", embedded::kDescription},
                  {"generated_at", embedded::kGeneratedAt}};
  }
  if (items.empty())
    throw std::runtime_error("nenhum *" + kSuffix + " em " +
                             (impl->directory.empty() ? std::string("(pacote)") : impl->directory));

  for (const auto& item : items) {
    const auto& schema = item.schema;
    if (!schema.contains("properties") || !schema["properties"].contains("schema") ||
        !schema["properties"]["schema"].contains("const") ||
        !schema["properties"]["schema"]["const"].is_string() ||
        schema["properties"]["schema"]["const"].get<std::string>().empty())
      throw std::runtime_error(item.file + ": sem properties.schema.const");
    const auto topic = schema["properties"]["schema"]["const"].get<std::string>();
    if (impl->by_topic.count(topic))
      throw std::runtime_error("tópico duplicado " + topic + ": " + impl->file_of[topic] +
                               " e " + item.file);
    check_keywords(schema, item.file);
    auto validator =
        std::make_shared<nlohmann::json_schema::json_validator>(nullptr, check_format);
    try {
      validator->set_root_schema(schema);
    } catch (const std::exception& ex) {
      throw std::runtime_error(item.file + ": schema inválido (" + ex.what() + ")");
    }
    impl->by_topic[topic] = std::move(validator);
    impl->file_of[topic] = item.file;
  }
  impl_ = std::move(impl);
}

std::vector<std::string> Validator::topics() const {
  std::vector<std::string> topics;
  for (const auto& kv : impl_->by_topic) topics.push_back(kv.first);  // std::map já ordena
  return topics;
}

const std::string& Validator::origin() const { return impl_->origin; }

json Validator::schemas_version() const {
  json info = {{"origin", impl_->origin},
               {"directory", impl_->directory.empty() ? json(nullptr) : json(impl_->directory)},
               {"count", impl_->by_topic.size()}};
  info.update(impl_->meta);
  return info;
}

std::vector<std::string> Validator::find_errors(const std::string& topic,
                                                const json& message) const {
  const auto it = impl_->by_topic.find(topic);
  if (it == impl_->by_topic.end()) return {"tópico desconhecido: " + topic};
  ErrorCollector collector;
  try {
    it->second->validate(message, collector);
  } catch (const std::exception& ex) {
    // falha ao checar (ex.: formato malformado) conta como violação, sem derrubar o processo
    collector.errors.push_back(std::string("(raiz): ") + ex.what());
  }
  std::sort(collector.errors.begin(), collector.errors.end());
  return collector.errors;
}

std::vector<std::string> Validator::find_message_errors(const json& message) const {
  if (!message.is_object() || !message.contains("schema"))
    return {"(raiz): mensagem sem o campo 'schema'"};
  if (!message["schema"].is_string()) return {"schema: deve ser texto"};
  return find_errors(message["schema"].get<std::string>(), message);
}

std::string Validator::validate(const json& message, const std::string& topic) const {
  std::string resolved = topic;
  if (resolved.empty() && message.is_object() && message.contains("schema") &&
      message["schema"].is_string())
    resolved = message["schema"].get<std::string>();
  if (resolved.empty()) throw ContractError("", {"(raiz): mensagem sem o campo 'schema'"});
  auto errors = find_errors(resolved, message);
  if (!errors.empty()) throw ContractError(resolved, std::move(errors));
  return resolved;
}

std::string publish(const Send& send, const Validator& validator, const json& message,
                    const std::string& topic) {
  const std::string resolved = validator.validate(message, topic);
  send(resolved, message.dump());
  return resolved;
}

}  // namespace ods
