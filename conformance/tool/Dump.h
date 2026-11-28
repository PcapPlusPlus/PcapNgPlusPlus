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

		/// What the tool found in the file a write produced.
		struct WrittenFile
		{
			bool exists = false;
			bool compressed = false;  ///< Written with compression; size and hash then depend on the zstd version
			uint64_t size = 0;
			std::string sha256;
		};

		/// Serializes a write as canonical JSON: whether the open succeeded, the written file (size and sha256, unless
		/// compressed) and @p reread, the read dump of the written file (null if there is no file).
		std::string dumpWriteResult(const WriteResult& result, const WrittenFile& file, const ReadResult* reread);
	}  // namespace conformance
}  // namespace pcpp
