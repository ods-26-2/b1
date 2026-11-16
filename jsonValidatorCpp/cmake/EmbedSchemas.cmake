# ods_embed_schemas(<schemas dir> <output header>)
# Gera um cabeçalho com os schemas embutidos, só com CMake (sem Python ou Node).
function(ods_embed_schemas SCHEMAS_DIR OUT_HEADER)
  file(GLOB_RECURSE files RELATIVE "${SCHEMAS_DIR}" "${SCHEMAS_DIR}/*.schema.json")
  list(SORT files)
  list(LENGTH files count)
  if(count EQUAL 0)
    message(FATAL_ERROR "ods: nenhum *.schema.json em ${SCHEMAS_DIR}. "
                        "Use -DODS_SCHEMAS_DIR=<pasta> ou compile de dentro do clone do b1.")
  endif()

  find_package(Git QUIET)
  set(commit "")
  set(description "")
  if(GIT_FOUND)
    execute_process(COMMAND "${GIT_EXECUTABLE}" rev-parse HEAD
      WORKING_DIRECTORY "${SCHEMAS_DIR}" OUTPUT_VARIABLE commit
      OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
    execute_process(COMMAND "${GIT_EXECUTABLE}" describe --tags --always --dirty
      WORKING_DIRECTORY "${SCHEMAS_DIR}" OUTPUT_VARIABLE description
      OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
  endif()
  string(TIMESTAMP now "%Y-%m-%dT%H:%M:%SZ" UTC)

  set(out "// GERADO por cmake/EmbedSchemas.cmake. Não edite.\n#pragma once\nnamespace ods::embedded {\n")
  string(APPEND out "struct Item { const char* file; const char* json; };\n")
  string(APPEND out "inline constexpr const char* kCommit = \"${commit}\";\n")
  string(APPEND out "inline constexpr const char* kDescription = \"${description}\";\n")
  string(APPEND out "inline constexpr const char* kGeneratedAt = \"${now}\";\n")
  string(APPEND out "inline constexpr Item kSchemas[] = {\n")
  foreach(file IN LISTS files)
    file(READ "${SCHEMAS_DIR}/${file}" body)
    string(APPEND out "{\"${file}\", R\"ODSJSON(${body})ODSJSON\"},\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${SCHEMAS_DIR}/${file}")
  endforeach()
  string(APPEND out "};\ninline constexpr unsigned kCount = ${count};\n}  // namespace ods::embedded\n")

  # só reescreve se mudou (ignora o carimbo de hora), para não recompilar à toa
  set(previous "")
  if(EXISTS "${OUT_HEADER}")
    file(READ "${OUT_HEADER}" previous)
  endif()
  string(REGEX REPLACE "kGeneratedAt = \"[^\"]*\"" "kGeneratedAt = \"\"" out_cmp "${out}")
  string(REGEX REPLACE "kGeneratedAt = \"[^\"]*\"" "kGeneratedAt = \"\"" previous_cmp "${previous}")
  if(NOT out_cmp STREQUAL previous_cmp)
    file(WRITE "${OUT_HEADER}" "${out}")
  endif()
  message(STATUS "ods: ${count} schemas embutidos (${description})")
endfunction()
