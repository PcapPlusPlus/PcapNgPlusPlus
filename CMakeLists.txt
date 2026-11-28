cmake_minimum_required(VERSION 3.14)

project(
  PcapNgPlusPlus
  VERSION 0.1.0
  DESCRIPTION "C++14 pcapng reader and writer, a drop-in replacement for LightPcapNg"
  LANGUAGES C CXX
)

set(CMAKE_CXX_STANDARD 14)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# The legacy LightPcapNg reference implementation, built with PcapPlusPlus's own CMakeLists.txt so that the flags and
# sources match what PcapPlusPlus ships. It defines the OBJECT library `light_pcapng` and the LIGHT_PCAPNG_ZSTD option.
add_subdirectory(legacy)
add_library(light_pcapng_legacy ALIAS light_pcapng)
