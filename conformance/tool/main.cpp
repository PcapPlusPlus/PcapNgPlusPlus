// pcapng-conformance-tool: runs one operation of one pcapng backend on one file and prints the canonical JSON dump.
// The pytest suite runs it once per case in a subprocess, so a crash or hang in a backend only fails that case.

#include "Backend.h"
#include "Dump.h"

#include <nlohmann/json.hpp>

#include <cstdio>
#include <cstring>
#include <fstream>
#include <iostream>
#include <string>

#ifdef _WIN32
#	include <fcntl.h>
#	include <io.h>
#endif

namespace
{
	// Exit codes. A dump is printed, and 0 returned, even when the backend fails to open the file: that is a result
	// to compare, not a tool error.
	constexpr int ExitOk = 0;
	constexpr int ExitUsage = 2;
	constexpr int ExitOutputError = 3;

	const char* const Usage =
	    "Usage: pcapng-conformance-tool read [--backend <name>] [--all-interfaces]\n"
	    "                               [--output <dump.json>] <file>\n"
	    "       pcapng-conformance-tool info\n"
	    "\n"
	    "read: reads <file> with the given backend (default: legacy) and prints the canonical JSON dump.\n"
	    "\n"
	    "  --backend <name>      Backend to run: legacy\n"
	    "  --all-interfaces      Open with read_all_interfaces set (PcapPlusPlus never sets it)\n"
	    "  --output <dump.json>  Write the dump to a file instead of stdout\n"
	    "\n"
	    "info: prints how the tool was built, as JSON, for the test runner.\n";

	int printInfo()
	{
		nlohmann::ordered_json info;
		info["formatVersion"] = pcpp::conformance::DumpFormatVersion;
		info["backends"] = pcpp::conformance::availableBackends();
#ifdef PCAPNGPP_HAS_ZSTD
		info["zstd"] = true;
#else
		info["zstd"] = false;
#endif
		std::string out = info.dump() + "\n";
		std::fwrite(out.data(), 1, out.size(), stdout);
		return std::fflush(stdout) == 0 ? ExitOk : ExitOutputError;
	}

	int usageError(const std::string& message)
	{
		std::cerr << "error: " << message << "\n\n" << Usage;
		return ExitUsage;
	}

	int writeOutput(const std::string& dump, const std::string& outputPath)
	{
		if (outputPath.empty())
		{
			std::fwrite(dump.data(), 1, dump.size(), stdout);
			return std::fflush(stdout) == 0 ? ExitOk : ExitOutputError;
		}

		std::ofstream file(outputPath, std::ios::binary);
		file << dump;
		file.close();
		if (!file)
		{
			std::cerr << "error: could not write " << outputPath << "\n";
			return ExitOutputError;
		}
		return ExitOk;
	}
}  // namespace

int main(int argc, char* argv[])
{
#ifdef _WIN32
	// Keep "\n" line endings on Windows, so dumps are byte-identical on every platform
	_setmode(_fileno(stdout), _O_BINARY);
#endif

	if (argc < 2 || std::strcmp(argv[1], "--help") == 0 || std::strcmp(argv[1], "-h") == 0)
	{
		std::cout << Usage;
		return argc < 2 ? ExitUsage : ExitOk;
	}

	std::string operation = argv[1];
	if (operation == "info")
	{
		return argc == 2 ? printInfo() : usageError("info takes no arguments");
	}
	if (operation != "read")
	{
		return usageError("unknown operation '" + operation + "'");
	}

	std::string backendName = "legacy";
	std::string outputPath;
	std::string inputPath;
	bool readAllInterfaces = false;

	for (int i = 2; i < argc; ++i)
	{
		std::string arg = argv[i];
		if (arg == "--backend" || arg == "--output")
		{
			if (i + 1 >= argc)
			{
				return usageError(arg + " needs a value");
			}
			(arg == "--backend" ? backendName : outputPath) = argv[++i];
		}
		else if (arg == "--all-interfaces")
		{
			readAllInterfaces = true;
		}
		else if (!arg.empty() && arg[0] == '-')
		{
			return usageError("unknown option '" + arg + "'");
		}
		else if (inputPath.empty())
		{
			inputPath = arg;
		}
		else
		{
			return usageError("only one input file is allowed");
		}
	}

	if (inputPath.empty())
	{
		return usageError("no input file");
	}

	std::unique_ptr<pcpp::conformance::Backend> backend = pcpp::conformance::createBackend(backendName);
	if (!backend)
	{
		return usageError("unknown backend '" + backendName + "'");
	}

	pcpp::conformance::ReadResult result = backend->read(inputPath, readAllInterfaces);
	return writeOutput(pcpp::conformance::dumpReadResult(result), outputPath);
}
