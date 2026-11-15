# Embute os schemas do repositório b1 em um cabeçalho C++ (configure time).
#   ods_embed_schemas(<pasta dos schemas> <cabeçalho de saída>)
# Só CMake: o build (inclusive na Jetson) não precisa de Python nem de Node.
function(ods_embed_schemas SCHEMAS_DIR OUT_HEADER)
  file(GLOB_RECURSE arquivos RELATIVE "${SCHEMAS_DIR}" "${SCHEMAS_DIR}/*.schema.json")
  list(SORT arquivos)
  list(LENGTH arquivos n)
  if(n EQUAL 0)
    message(FATAL_ERROR "ods: nenhum *.schema.json em ${SCHEMAS_DIR}. "
                        "Use -DODS_SCHEMAS_DIR=<pasta> ou compile de dentro do clone do b1.")
  endif()

  find_package(Git QUIET)
  set(commit "")
  set(descricao "")
  if(GIT_FOUND)
    execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD
      WORKING_DIRECTORY "${SCHEMAS_DIR}" OUTPUT_VARIABLE commit
      OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
    execute_process(COMMAND "${GIT_EXECUTABLE}" describe --tags --always --dirty
      WORKING_DIRECTORY "${SCHEMAS_DIR}" OUTPUT_VARIABLE descricao
      OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
  endif()
  string(TIMESTAMP agora "%Y-%m-%dT%H:%M:%SZ" UTC)

  set(c "// GERADO por cmake/EmbedSchemas.cmake. Não edite.\n#pragma once\nnamespace ods::embedded {\n")
  string(APPEND c "struct Item { const char* arquivo; const char* json; };\n")
  string(APPEND c "inline constexpr const char* kCommit = \"${commit}\";\n")
  string(APPEND c "inline constexpr const char* kDescricao = \"${descricao}\";\n")
  string(APPEND c "inline constexpr const char* kGeradoEm = \"${agora}\";\n")
  string(APPEND c "inline constexpr Item kSchemas[] = {\n")
  foreach(f IN LISTS arquivos)
    file(READ "${SCHEMAS_DIR}/${f}" corpo)
    string(APPEND c "{\"${f}\", R\"ODSJSON(${corpo})ODSJSON\"},\n")
    # mudou um schema -> o CMake reconfigura e o cabeçalho é regerado
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${SCHEMAS_DIR}/${f}")
  endforeach()
  string(APPEND c "};\ninline constexpr unsigned kQuantidade = ${n};\n}  // namespace ods::embedded\n")

  # reescreve só se mudou (evita recompilar tudo à toa); ignora o carimbo de hora
  set(antigo "")
  if(EXISTS "${OUT_HEADER}")
    file(READ "${OUT_HEADER}" antigo)
  endif()
  string(REGEX REPLACE "kGeradoEm = \"[^\"]*\"" "kGeradoEm = \"\"" c_cmp "${c}")
  string(REGEX REPLACE "kGeradoEm = \"[^\"]*\"" "kGeradoEm = \"\"" a_cmp "${antigo}")
  if(NOT c_cmp STREQUAL a_cmp)
    file(WRITE "${OUT_HEADER}" "${c}")
  endif()
  message(STATUS "ods: ${n} schemas embutidos (${descricao})")
endfunction()
