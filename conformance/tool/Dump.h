#pragma once

#include "Backend.h"

#include <string>

namespace pcpp
{
	namespace conformance
	{
		/// Version of the dump format. Bump it whenever the output changes for the same input, and regenerate goldens.
		constexpr int DumpFormatVersion = 1;

		/// Packet data up to this many bytes is dumped as hex; longer data is dumped as its SHA-256.
		constexpr size_t MaxHexDataLength = 256;

		/// Serializes @p result as canonical JSON: fixed key order, two-space indent, one line per packet, "\n" line
		/// endings and a trailing newline. The format is described in conformance/README.md.
		std::string dumpReadResult(const ReadResult& result);
	}  // namespace conformance
}  // namespace pcpp
