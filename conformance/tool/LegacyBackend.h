#pragma once

#include "Backend.h"

namespace pcpp
{
	namespace conformance
	{
		/// Runs the legacy LightPcapNg C code through the same ext API calls PcapPlusPlus makes.
		class LegacyBackend : public Backend
		{
		public:
			ReadResult read(const std::string& path, bool readAllInterfaces) override;
			WriteResult write(const std::string& path, const WriteScript& script) override;
			AppendResult append(const std::string& path, const AppendScript& script) override;
		};
	}  // namespace conformance
}  // namespace pcpp
