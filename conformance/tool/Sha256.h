#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace pcpp
{
	namespace conformance
	{
		/// Returns the SHA-256 digest of @p size bytes at @p data as 64 lowercase hex characters.
		std::string sha256Hex(const uint8_t* data, size_t size);
	}  // namespace conformance
}  // namespace pcpp
