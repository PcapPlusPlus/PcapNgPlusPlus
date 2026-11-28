add_executable(
  pcapng-conformance-tool
  Backend.cpp
  Dump.cpp
  LegacyBackend.cpp
  Sha256.cpp
  main.cpp
)

target_link_libraries(pcapng-conformance-tool PRIVATE light_pcapng_legacy nlohmann_json)

if(MSVC)
  target_compile_options(pcapng-conformance-tool PRIVATE /W4)
else()
  target_compile_options(pcapng-conformance-tool PRIVATE -Wall -Wextra -Wpedantic)
endif()
