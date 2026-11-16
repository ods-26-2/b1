cmake_minimum_required(VERSION 3.16)
project(ods_validator VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(ODS_IS_TOP_LEVEL ON)
else()
  set(ODS_IS_TOP_LEVEL OFF)
endif()

option(ODS_BUILD_CLI "Compila o ods-validate" ${ODS_IS_TOP_LEVEL})
option(ODS_BUILD_TESTS "Compila os testes" ${ODS_IS_TOP_LEVEL})
set(ODS_SCHEMAS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../schemas" CACHE PATH
    "Pasta dos schemas a embutir (padrão: ../schemas do clone do b1)")
set(ODS_EXAMPLES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/../examples" CACHE PATH
    "Pasta dos exemplos compartilhados (usada nos testes)")

# dependências: usa as do sistema se houver; senão baixa (versões fixas)
include(FetchContent)
find_package(nlohmann_json 3.9 QUIET)
if(NOT nlohmann_json_FOUND)
  set(JSON_BuildTests OFF CACHE INTERNAL "")
  set(JSON_Install OFF CACHE INTERNAL "")
  FetchContent_Declare(nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.3 GIT_SHALLOW TRUE)
  FetchContent_MakeAvailable(nlohmann_json)
endif()

find_package(nlohmann_json_schema_validator QUIET)
if(NOT nlohmann_json_schema_validator_FOUND)
  set(JSON_VALIDATOR_INSTALL OFF CACHE INTERNAL "")
  set(JSON_VALIDATOR_BUILD_TESTS OFF CACHE INTERNAL "")
  set(JSON_VALIDATOR_BUILD_EXAMPLES OFF CACHE INTERNAL "")
  FetchContent_Declare(json_schema_validator
    GIT_REPOSITORY https://github.com/pboettch/json-schema-validator.git
    GIT_TAG 2.3.0 GIT_SHALLOW TRUE)
  FetchContent_MakeAvailable(json_schema_validator)
endif()
if(TARGET nlohmann_json_schema_validator::validator)
  set(ODS_SV_TARGET nlohmann_json_schema_validator::validator)
else()
  set(ODS_SV_TARGET nlohmann_json_schema_validator)
endif()

include(cmake/EmbedSchemas.cmake)
set(ODS_GEN_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
ods_embed_schemas("${ODS_SCHEMAS_DIR}" "${ODS_GEN_DIR}/ods_schemas.hpp")

add_library(ods_validator STATIC src/validator.cpp)
add_library(ods::validator ALIAS ods_validator)
target_include_directories(ods_validator
  PUBLIC  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  PRIVATE ${ODS_GEN_DIR})
target_link_libraries(ods_validator PUBLIC nlohmann_json::nlohmann_json ${ODS_SV_TARGET})
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(ods_validator PRIVATE -Wall -Wextra)
endif()

if(ODS_BUILD_CLI)
  add_executable(ods-validate src/cli.cpp)
  target_link_libraries(ods-validate PRIVATE ods::validator)
endif()

if(ODS_BUILD_TESTS)
  enable_testing()
  add_executable(test_ods tests/test_ods.cpp)
  target_link_libraries(test_ods PRIVATE ods::validator)
  target_compile_definitions(test_ods PRIVATE
    ODS_EXAMPLES_DIR="${ODS_EXAMPLES_DIR}" ODS_SCHEMAS_DIR_PATH="${ODS_SCHEMAS_DIR}")
  add_test(NAME ods COMMAND test_ods)
  if(ODS_BUILD_CLI)
    # regressão: --info já deu segfault
    add_test(NAME ods_cli_info COMMAND ods-validate --info)
    set_tests_properties(ods_cli_info PROPERTIES PASS_REGULAR_EXPRESSION "count: 56")
  endif()
endif()
