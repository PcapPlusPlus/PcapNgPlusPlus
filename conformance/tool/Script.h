#pragma once

#include "Backend.h"

#include <stdexcept>
#include <string>

namespace pcpp
{
	namespace conformance
	{
		/// A write script that isn't valid. The message says what and where.
		class ScriptError : public std::runtime_error
		{
		public:
			using std::runtime_error::runtime_error;
		};

		/// Parses a write script (the format is in conformance/README.md).
		/// @param[in] text The script's JSON.
		/// @throws ScriptError if the script is invalid.
		WriteScript parseWriteScript(const std::string& text);
	}  // namespace conformance
}  // namespace pcpp
