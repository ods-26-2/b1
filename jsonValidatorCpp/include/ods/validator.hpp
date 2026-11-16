#pragma once

#include <functional>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace ods {

inline constexpr const char* kEnvSchemasDir = "ODS_SCHEMAS_DIR";

class ContractError : public std::runtime_error {
 public:
  ContractError(std::string topic, std::vector<std::string> errors);
  const std::string& topic() const { return topic_; }
  const std::vector<std::string>& errors() const { return errors_; }

 private:
  std::string topic_;
  std::vector<std::string> errors_;
};

class Validator {
 public:
  // diretório vazio: usa ODS_SCHEMAS_DIR e, se não houver, os schemas embutidos
  explicit Validator(const std::string& directory = "");

  std::vector<std::string> topics() const;
  const std::string& origin() const;  // "argument", "ODS_SCHEMAS_DIR" ou "package"
  nlohmann::json schemas_version() const;

  std::vector<std::string> find_errors(const std::string& topic,
                                       const nlohmann::json& message) const;
  std::vector<std::string> find_message_errors(const nlohmann::json& message) const;

  std::string validate(const nlohmann::json& message, const std::string& topic = "") const;

 private:
  struct Impl;
  std::shared_ptr<const Impl> impl_;
};

using Send = std::function<void(const std::string& topic, const std::string& data)>;

std::string publish(const Send& send, const Validator& validator,
                    const nlohmann::json& message, const std::string& topic = "");

}  // namespace ods
