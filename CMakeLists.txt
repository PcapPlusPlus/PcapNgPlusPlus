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

# Default to Release like PcapPlusPlus does. Legacy behavior depends on it: in Debug, legacy's assert() calls abort on
# some malformed inputs that a Release build reads through, and goldens must reflect the build PcapPlusPlus ships.
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE "Release" CACHE STRING "Choose the type of build." FORCE)
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS "Debug" "Release" "RelWithDebInfo" "MinSizeRel")
endif()

# Same as PcapPlusPlus's PCAPPP_BUILD_COVERAGE: instruments everything for gcov, so gcovr can report on legacy/
option(PCAPNGPP_BUILD_COVERAGE "Build with gcov coverage instrumentation" OFF)
if(PCAPNGPP_BUILD_COVERAGE)
  add_compile_options(--coverage)
  add_link_options(--coverage)
endif()

# The legacy LightPcapNg reference implementation, built with PcapPlusPlus's own CMakeLists.txt so that the flags and
# sources match what PcapPlusPlus ships. It defines the OBJECT library `light_pcapng` and the LIGHT_PCAPNG_ZSTD option.
add_subdirectory(legacy)
add_library(light_pcapng_legacy ALIAS light_pcapng)

option(PCAPNGPP_BUILD_CONFORMANCE "Build the conformance tool" ON)
if(PCAPNGPP_BUILD_CONFORMANCE)
  add_subdirectory(conformance/third_party)
  add_subdirectory(conformance/tool)
endif()
