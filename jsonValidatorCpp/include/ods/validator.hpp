// Validador de mensagens do barramento (entregável B1 da TRA-1).
//
// A chave de busca é o valor de properties.schema.const de cada schema, que é
// o nome do tópico. Nome de arquivo e pasta não importam.
//
// Onde os schemas são procurados, nesta ordem:
//   1. argumento Validator("pasta")
//   2. variável de ambiente ODS_SCHEMAS_DIR
//   3. cópia embutida na biblioteca (gerada no build a partir do repositório b1)
#pragma once

#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace ods {

inline constexpr const char* kEnvPasta = "ODS_SCHEMAS_DIR";

// Mensagem fora do contrato. erros() lista cada violação.
class ContractError : public std::runtime_error {
 public:
  ContractError(std::string topico, std::vector<std::string> erros);
  const std::string& topico() const { return topico_; }
  const std::vector<std::string>& erros() const { return erros_; }

 private:
  std::string topico_;
  std::vector<std::string> erros_;
};

class Validator {
 public:
  // pasta vazia: usa ODS_SCHEMAS_DIR e, se não houver, a cópia embutida.
  explicit Validator(const std::string& pasta = "");

  std::vector<std::string> topicos() const;
  const std::string& origem() const;  // "argumento", "ODS_SCHEMAS_DIR" ou "pacote"

  // De onde vieram os schemas e, no embutido, de qual commit do b1.
  nlohmann::json schemas_version() const;

  // Devolve a lista de erros. Vazia = mensagem válida.
  std::vector<std::string> validar(const std::string& topico,
                                   const nlohmann::json& mensagem) const;

  // Descobre o tópico pelo campo "schema" da própria mensagem.
  std::vector<std::string> validar_mensagem(const nlohmann::json& mensagem) const;

  // Lança ContractError se inválida. Devolve o tópico.
  std::string validate(const nlohmann::json& mensagem,
                       const std::string& topico = "") const;

 private:
  struct Impl;
  std::shared_ptr<const Impl> impl_;
};

// enviar(topico, bytes): qualquer função que publica no Kafka.
using Enviar = std::function<void(const std::string& topico, const std::string& dados)>;

// Valida e só então envia. Mensagem inválida nunca chega ao broker.
std::string publish(const Enviar& enviar, const Validator& validador,
                    const nlohmann::json& mensagem, const std::string& topico = "");

}  // namespace ods
