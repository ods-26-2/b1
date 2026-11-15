#include "ods/validator.hpp"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <sstream>

#include <nlohmann/json-schema.hpp>

#include "ods_schemas.hpp"  // gerado em build por cmake/EmbedSchemas.cmake

namespace fs = std::filesystem;
using nlohmann::json;

namespace ods {

namespace {

const std::string kSufixo = ".schema.json";

// A biblioteca de validação em C++ implementa o JSON Schema draft-07. Os
// schemas declaram 2020-12, mas hoje só usam palavras que existem nos dois.
// Se alguém passar a usar uma palavra só do 2020-12, o C++ a ignoraria em
// silêncio e divergiria de Python/TypeScript; por isso recusamos na carga.
const std::set<std::string>& palavras_proibidas() {
  static const std::set<std::string> p{
      "prefixItems",       "unevaluatedProperties", "unevaluatedItems", "dependentRequired",
      "dependentSchemas",  "$defs",                 "$dynamicRef",      "$dynamicAnchor",
      "$anchor",           "minContains",           "maxContains",      "contentSchema"};
  return p;
}

void verificar_palavras(const json& s, const std::string& arquivo) {
  if (!s.is_object()) return;
  for (const auto& kv : s.items()) {
    if (palavras_proibidas().count(kv.key())) {
      throw std::runtime_error(arquivo + ": a palavra '" + kv.key() +
                               "' é só do JSON Schema 2020-12 e esta biblioteca C++ "
                               "(draft-07) não a implementa");
    }
  }
  for (const char* k : {"properties", "patternProperties"}) {
    if (s.contains(k) && s[k].is_object())
      for (const auto& kv : s[k].items()) verificar_palavras(kv.value(), arquivo);
  }
  for (const char* k : {"allOf", "anyOf", "oneOf"}) {
    if (s.contains(k) && s[k].is_array())
      for (const auto& e : s[k]) verificar_palavras(e, arquivo);
  }
  for (const char* k : {"if", "then", "else", "not", "additionalProperties", "contains"}) {
    if (s.contains(k)) verificar_palavras(s[k], arquivo);
  }
  if (s.contains("items")) {
    if (s["items"].is_array())
      for (const auto& e : s["items"]) verificar_palavras(e, arquivo);
    else
      verificar_palavras(s["items"], arquivo);
  }
}

// Sem verificador, a biblioteca trata "format" como anotação e não valida nada.
// Formatos que não conhecemos são ignorados, como no jsonschema (Python).
void checar_formato(const std::string& formato, const std::string& valor) {
  static const std::set<std::string> conhecidos{"date-time", "date", "time", "uri", "email",
                                                "ipv4",      "ipv6", "uuid", "hostname"};
  if (conhecidos.count(formato))
    nlohmann::json_schema::default_string_format_check(formato, valor);
}

class Coletor : public nlohmann::json_schema::basic_error_handler {
 public:
  void error(const json::json_pointer& ptr, const json& instance,
             const std::string& message) override {
    nlohmann::json_schema::basic_error_handler::error(ptr, instance, message);
    std::string onde = ptr.to_string();
    if (!onde.empty() && onde[0] == '/') onde.erase(0, 1);
    if (onde.empty()) onde = "(raiz)";
    erros.push_back(onde + ": " + message);
  }
  std::vector<std::string> erros;
};

struct Item {
  std::string arquivo;
  json schema;
};

std::string ler_arquivo(const fs::path& p) {
  std::ifstream in(p, std::ios::binary);
  if (!in) throw std::runtime_error("não consegui abrir " + p.string());
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

bool termina_com(const std::string& s, const std::string& sufixo) {
  return s.size() >= sufixo.size() &&
         s.compare(s.size() - sufixo.size(), std::string::npos, sufixo) == 0;
}

}  // namespace

ContractError::ContractError(std::string topico, std::vector<std::string> erros)
    : std::runtime_error([&] {
        std::string m = topico + ": ";
        for (size_t i = 0; i < erros.size(); ++i) m += (i ? "; " : "") + erros[i];
        return m;
      }()),
      topico_(std::move(topico)),
      erros_(std::move(erros)) {}

struct Validator::Impl {
  std::string origem;
  std::string pasta;
  json meta = json::object();
  std::map<std::string, std::shared_ptr<nlohmann::json_schema::json_validator>> por_topico;
  std::map<std::string, std::string> arquivo_de;
};

Validator::Validator(const std::string& pasta_arg) {
  auto impl = std::make_shared<Impl>();
  std::vector<Item> itens;

  std::string dir = pasta_arg;
  if (!dir.empty()) {
    impl->origem = "argumento";
  } else if (const char* env = std::getenv(kEnvPasta); env && *env) {
    dir = env;
    impl->origem = kEnvPasta;
  }

  if (!dir.empty()) {
    impl->pasta = dir;
    std::vector<fs::path> achados;
    for (const auto& e : fs::recursive_directory_iterator(dir)) {
      if (e.is_regular_file() && termina_com(e.path().filename().string(), kSufixo))
        achados.push_back(e.path());
    }
    std::sort(achados.begin(), achados.end());
    for (const auto& p : achados) {
      try {
        itens.push_back({fs::relative(p, dir).generic_string(), json::parse(ler_arquivo(p))});
      } catch (const json::exception& ex) {
        throw std::runtime_error(p.string() + ": JSON inválido (" + ex.what() + ")");
      }
    }
    const fs::path meta = fs::path(dir) / "VERSAO.json";
    if (fs::exists(meta)) impl->meta = json::parse(ler_arquivo(meta));
  } else {
    impl->origem = "pacote";
    for (const auto& it : embedded::kSchemas)
      itens.push_back({it.arquivo, json::parse(it.json)});
    impl->meta = {{"commit", embedded::kCommit},
                  {"descricao", embedded::kDescricao},
                  {"gerado_em", embedded::kGeradoEm}};
  }
  if (itens.empty())
    throw std::runtime_error("nenhum *" + kSufixo + " em " +
                             (impl->pasta.empty() ? std::string("(pacote)") : impl->pasta));

  for (const auto& it : itens) {
    const auto& s = it.schema;
    if (!s.contains("properties") || !s["properties"].contains("schema") ||
        !s["properties"]["schema"].contains("const") ||
        !s["properties"]["schema"]["const"].is_string() ||
        s["properties"]["schema"]["const"].get<std::string>().empty())
      throw std::runtime_error(it.arquivo + ": sem properties.schema.const");
    const auto topico = s["properties"]["schema"]["const"].get<std::string>();
    if (impl->por_topico.count(topico))
      throw std::runtime_error("tópico duplicado " + topico + ": " + impl->arquivo_de[topico] +
                               " e " + it.arquivo);
    verificar_palavras(s, it.arquivo);
    auto v = std::make_shared<nlohmann::json_schema::json_validator>(nullptr, checar_formato);
    try {
      v->set_root_schema(s);
    } catch (const std::exception& ex) {
      throw std::runtime_error(it.arquivo + ": schema inválido (" + ex.what() + ")");
    }
    impl->por_topico[topico] = std::move(v);
    impl->arquivo_de[topico] = it.arquivo;
  }
  impl_ = std::move(impl);
}

std::vector<std::string> Validator::topicos() const {
  std::vector<std::string> t;
  for (const auto& kv : impl_->por_topico) t.push_back(kv.first);  // std::map: já ordenado
  return t;
}

const std::string& Validator::origem() const { return impl_->origem; }

json Validator::schemas_version() const {
  json j = {{"origem", impl_->origem},
            {"pasta", impl_->pasta.empty() ? json(nullptr) : json(impl_->pasta)},
            {"quantidade", impl_->por_topico.size()}};
  j.update(impl_->meta);
  return j;
}

std::vector<std::string> Validator::validar(const std::string& topico,
                                            const json& mensagem) const {
  const auto it = impl_->por_topico.find(topico);
  if (it == impl_->por_topico.end()) return {"tópico desconhecido: " + topico};
  Coletor c;
  try {
    it->second->validate(mensagem, c);
  } catch (const std::exception& ex) {
    // erro ao checar (ex.: formato malformado) conta como violação; não derruba o processo
    c.erros.push_back(std::string("(raiz): ") + ex.what());
  }
  std::sort(c.erros.begin(), c.erros.end());
  return c.erros;
}

std::vector<std::string> Validator::validar_mensagem(const json& mensagem) const {
  if (!mensagem.is_object() || !mensagem.contains("schema"))
    return {"(raiz): mensagem sem o campo 'schema'"};
  if (!mensagem["schema"].is_string()) return {"schema: deve ser texto"};
  return validar(mensagem["schema"].get<std::string>(), mensagem);
}

std::string Validator::validate(const json& mensagem, const std::string& topico) const {
  std::string t = topico;
  if (t.empty() && mensagem.is_object() && mensagem.contains("schema") &&
      mensagem["schema"].is_string())
    t = mensagem["schema"].get<std::string>();
  if (t.empty()) throw ContractError("", {"(raiz): mensagem sem o campo 'schema'"});
  auto erros = validar(t, mensagem);
  if (!erros.empty()) throw ContractError(t, std::move(erros));
  return t;
}

std::string publish(const Enviar& enviar, const Validator& validador, const json& mensagem,
                    const std::string& topico) {
  const std::string t = validador.validate(mensagem, topico);
  enviar(t, mensagem.dump());
  return t;
}

}  // namespace ods
