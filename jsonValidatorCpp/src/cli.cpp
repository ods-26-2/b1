#include <fstream>
#include <iostream>
#include <sstream>

#include "ods/validator.hpp"

int main(int argc, char** argv) {
  std::string schemas, topic;
  bool info = false;
  std::vector<std::string> files;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    if (arg == "--schemas" && i + 1 < argc) schemas = argv[++i];
    else if (arg == "--topic" && i + 1 < argc) topic = argv[++i];
    else if (arg == "--info") info = true;
    else files.push_back(arg);
  }
  try {
    ods::Validator validator(schemas);
    if (info) {
      // items() de um temporário apontaria para memória liberada
      const nlohmann::json version = validator.schemas_version();
      for (const auto& kv : version.items())
        std::cout << kv.key() << ": "
                  << (kv.value().is_string() ? kv.value().get<std::string>() : kv.value().dump())
                  << "\n";
      if (files.empty()) return 0;
    }
    if (files.empty()) {
      std::cerr << "informe ao menos um arquivo (ou use --info)\n";
      return 2;
    }
    int status = 0;
    for (const auto& name : files) {
      std::ostringstream ss;
      if (name == "-") {
        ss << std::cin.rdbuf();
      } else {
        std::ifstream in(name, std::ios::binary);
        if (!in) {
          std::cout << name << ": não consegui abrir\n";
          status = 1;
          continue;
        }
        ss << in.rdbuf();
      }
      nlohmann::json message = nlohmann::json::parse(ss.str(), nullptr, false);
      if (message.is_discarded()) {
        std::cout << name << ": JSON inválido\n";
        status = 1;
        continue;
      }
      const auto errors =
          topic.empty() ? validator.find_message_errors(message) : validator.find_errors(topic, message);
      if (errors.empty()) {
        std::cout << name << ": ok\n";
      } else {
        status = 1;
        std::cout << name << ": INVÁLIDA\n";
        for (const auto& e : errors) std::cout << "  - " << e << "\n";
      }
    }
    return status;
  } catch (const std::exception& e) {
    std::cerr << "erro: " << e.what() << "\n";
    return 2;
  }
}
