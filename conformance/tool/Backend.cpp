#include "Backend.h"

#include "LegacyBackend.h"

namespace pcpp
{
	namespace conformance
	{
		std::unique_ptr<Backend> createBackend(const std::string& name)
		{
			if (name == "legacy")
			{
				return std::unique_ptr<Backend>(new LegacyBackend());
			}
			return nullptr;
		}

		std::vector<std::string> availableBackends()
		{
			return { "legacy" };
		}
	}  // namespace conformance
}  // namespace pcpp
