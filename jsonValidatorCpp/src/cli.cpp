// ods-validar [--schemas PASTA] [--topico T] [--info] arquivo.json [...]  (- = stdin)
#include <fstream>
#include <iostream>
#include <sstream>

#include "ods/validator.hpp"

int main(int argc, char** argv) {
  std::string schemas, topico;
  bool info = false;
  std::vector<std::string> arquivos;
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--schemas" && i + 1 < argc) schemas = argv[++i];
    else if (a == "--topico" && i + 1 < argc) topico = argv[++i];
    else if (a == "--info") info = true;
    else arquivos.push_back(a);
  }
  try {
    ods::Validator val(schemas);
    if (info) {
      // guardar numa variável: items() de um temporário ficaria apontando para memória liberada
      const nlohmann::json versao = val.schemas_version();
      for (const auto& kv : versao.items())
        std::cout << kv.key() << ": "
                  << (kv.value().is_string() ? kv.value().get<std::string>() : kv.value().dump())
                  << "\n";
      if (arquivos.empty()) return 0;
    }
    if (arquivos.empty()) {
      std::cerr << "informe ao menos um arquivo (ou use --info)\n";
      return 2;
    }
    int rc = 0;
    for (const auto& nome : arquivos) {
      std::ostringstream ss;
      if (nome == "-") {
        ss << std::cin.rdbuf();
      } else {
        std::ifstream in(nome, std::ios::binary);
        if (!in) {
          std::cout << nome << ": não consegui abrir\n";
          rc = 1;
          continue;
        }
        ss << in.rdbuf();
      }
      nlohmann::json msg = nlohmann::json::parse(ss.str(), nullptr, false);
      if (msg.is_discarded()) {
        std::cout << nome << ": JSON inválido\n";
        rc = 1;
        continue;
      }
      const auto erros = topico.empty() ? val.validar_mensagem(msg) : val.validar(topico, msg);
      if (erros.empty()) {
        std::cout << nome << ": ok\n";
      } else {
        rc = 1;
        std::cout << nome << ": INVÁLIDA\n";
        for (const auto& e : erros) std::cout << "  - " << e << "\n";
      }
    }
    return rc;
  } catch (const std::exception& e) {
    std::cerr << "erro: " << e.what() << "\n";
    return 2;
  }
}
