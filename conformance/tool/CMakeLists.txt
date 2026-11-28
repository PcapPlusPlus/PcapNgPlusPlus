add_executable(
  pcapng-conformance-tool
  Backend.cpp
  Dump.cpp
  LegacyBackend.cpp
  Sha256.cpp
  main.cpp
)

target_link_libraries(pcapng-conformance-tool PRIVATE light_pcapng_legacy nlohmann_json)

# Reported by `pcapng-conformance-tool info`, so the test runner can skip .zst cases on builds without zstd
if(LIGHT_PCAPNG_ZSTD)
  target_compile_definitions(pcapng-conformance-tool PRIVATE PCAPNGPP_HAS_ZSTD)
endif()

if(MSVC)
  target_compile_options(pcapng-conformance-tool PRIVATE /W4)
else()
  target_compile_options(pcapng-conformance-tool PRIVATE -Wall -Wextra -Wpedantic)
endif()
