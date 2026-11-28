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
		};
	}  // namespace conformance
}  // namespace pcpp
