# Header-only; SYSTEM so the tool's warning flags don't apply to vendored code
add_library(nlohmann_json INTERFACE)
target_include_directories(nlohmann_json SYSTEM INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})
