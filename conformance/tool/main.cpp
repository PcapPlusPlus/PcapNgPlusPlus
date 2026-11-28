// pcapng-conformance-tool: runs one operation of one pcapng backend and prints the canonical JSON dump.
// The pytest suite runs it once per case in a subprocess, so a crash or hang in a backend only fails that case.

#include "Backend.h"
#include "Dump.h"
#include "Script.h"
#include "Sha256.h"

#include <nlohmann/json.hpp>

#include <cstdio>
#include <cstring>
#include <ctime>
#include <fstream>
#include <iostream>
#include <iterator>
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
	    "       pcapng-conformance-tool write [--backend <name>] --script <script.json> --output-dir <dir>\n"
	    "                               [--output <dump.json>]\n"
	    "       pcapng-conformance-tool append [--backend <name>] --script <script.json> --file <file>\n"
	    "                               [--output <dump.json>]\n"
	    "       pcapng-conformance-tool info\n"
	    "\n"
	    "read: reads <file> with the given backend (default: legacy) and prints the canonical JSON dump.\n"
	    "write: runs a write script, writing its file into <dir>, then prints a dump of the result,\n"
	    "       including a read of the written file.\n"
	    "append: opens <file> for appending and runs a script's steps on it (the file is modified),\n"
	    "        then prints a dump of the result, including a read of the file.\n"
	    "info: prints how the tool was built, as JSON, for the test runner.\n"
	    "\n"
	    "  --backend <name>      Backend to run: legacy\n"
	    "  --all-interfaces      Open with read_all_interfaces set (PcapPlusPlus never sets it)\n"
	    "  --script <file>       The write or append script (see conformance/README.md)\n"
	    "  --file <file>         The existing file to append to\n"
	    "  --output-dir <dir>    Directory the write script's file is created in\n"
	    "  --output <dump.json>  Write the dump to a file instead of stdout\n";

	bool hasZstd()
	{
#ifdef PCAPNGPP_HAS_ZSTD
		return true;
#else
		return false;
#endif
	}

	int printInfo()
	{
		nlohmann::ordered_json info;
		info["formatVersion"] = pcpp::conformance::DumpFormatVersion;
		info["backends"] = pcpp::conformance::availableBackends();
		info["operations"] = { "read", "write", "append" };
		info["zstd"] = hasZstd();
		// Width of timespec::tv_sec, which the ext API returns packet timestamps in. It is 32 bits on some platforms
		// (for example 32-bit MinGW), where timestamps after January 2038 wrap around.
		info["timestampSecBits"] = sizeof(timespec::tv_sec) * 8;
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

	bool readFile(const std::string& path, std::string& contents)
	{
		std::ifstream file(path, std::ios::binary);
		if (!file)
		{
			return false;
		}
		contents.assign(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
		return true;
	}

	struct Options
	{
		std::string backendName = "legacy";
		std::string outputPath;
		std::string inputPath;
		std::string scriptPath;
		std::string outputDir;
		std::string appendPath;
		bool readAllInterfaces = false;
	};

	int runRead(pcpp::conformance::Backend& backend, const Options& options)
	{
		if (options.inputPath.empty())
		{
			return usageError("read needs an input file");
		}
		pcpp::conformance::ReadResult result = backend.read(options.inputPath, options.readAllInterfaces);
		return writeOutput(pcpp::conformance::dumpReadResult(result), options.outputPath);
	}

	int runWrite(pcpp::conformance::Backend& backend, const Options& options)
	{
		if (options.scriptPath.empty() || options.outputDir.empty())
		{
			return usageError("write needs --script and --output-dir");
		}

		std::string scriptText;
		if (!readFile(options.scriptPath, scriptText))
		{
			return usageError("could not read the script " + options.scriptPath);
		}
		pcpp::conformance::WriteScript script;
		try
		{
			script = pcpp::conformance::parseWriteScript(scriptText);
		}
		catch (const pcpp::conformance::ScriptError& error)
		{
			return usageError(options.scriptPath + ": " + error.what());
		}

		const std::string path = options.outputDir + "/" + script.fileName;
		pcpp::conformance::WriteResult result = backend.write(path, script);

		pcpp::conformance::WrittenFile file;
		std::string contents;
		file.exists = readFile(path, contents);
		if (file.exists)
		{
			// Without zstd, legacy ignores the compression level and writes a plain file
			file.compressed = script.compressionLevel > 0 && hasZstd();
			file.size = contents.size();
			file.sha256 =
			    pcpp::conformance::sha256Hex(reinterpret_cast<const uint8_t*>(contents.data()), contents.size());
		}

		// Read the file back the way PcapPlusPlus would, with the same backend
		pcpp::conformance::ReadResult reread;
		if (file.exists)
		{
			reread = backend.read(path, false);
		}
		return writeOutput(pcpp::conformance::dumpWriteResult(result, file, file.exists ? &reread : nullptr),
		                   options.outputPath);
	}

	int runAppend(pcpp::conformance::Backend& backend, const Options& options)
	{
		if (options.scriptPath.empty() || options.appendPath.empty())
		{
			return usageError("append needs --script and --file");
		}

		std::string scriptText;
		if (!readFile(options.scriptPath, scriptText))
		{
			return usageError("could not read the script " + options.scriptPath);
		}
		pcpp::conformance::AppendScript script;
		try
		{
			script = pcpp::conformance::parseAppendScript(scriptText);
		}
		catch (const pcpp::conformance::ScriptError& error)
		{
			return usageError(options.scriptPath + ": " + error.what());
		}

		pcpp::conformance::AppendResult result = backend.append(options.appendPath, script);

		// Append never compresses, so the bytes are compared even for a .zst file
		pcpp::conformance::WrittenFile file;
		std::string contents;
		file.exists = readFile(options.appendPath, contents);
		if (file.exists)
		{
			file.size = contents.size();
			file.sha256 =
			    pcpp::conformance::sha256Hex(reinterpret_cast<const uint8_t*>(contents.data()), contents.size());
		}

		pcpp::conformance::ReadResult reread;
		if (file.exists)
		{
			reread = backend.read(options.appendPath, false);
		}
		return writeOutput(pcpp::conformance::dumpAppendResult(result, file, file.exists ? &reread : nullptr),
		                   options.outputPath);
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
	if (operation != "read" && operation != "write" && operation != "append")
	{
		return usageError("unknown operation '" + operation + "'");
	}

	Options options;
	for (int i = 2; i < argc; ++i)
	{
		std::string arg = argv[i];
		std::string* value = nullptr;
		if (arg == "--backend")
		{
			value = &options.backendName;
		}
		else if (arg == "--output")
		{
			value = &options.outputPath;
		}
		else if (arg == "--script" && operation != "read")
		{
			value = &options.scriptPath;
		}
		else if (arg == "--output-dir" && operation == "write")
		{
			value = &options.outputDir;
		}
		else if (arg == "--file" && operation == "append")
		{
			value = &options.appendPath;
		}

		if (value != nullptr)
		{
			if (i + 1 >= argc)
			{
				return usageError(arg + " needs a value");
			}
			*value = argv[++i];
		}
		else if (arg == "--all-interfaces" && operation == "read")
		{
			options.readAllInterfaces = true;
		}
		else if (!arg.empty() && arg[0] == '-')
		{
			return usageError("unknown option '" + arg + "' for " + operation);
		}
		else if (operation == "read" && options.inputPath.empty())
		{
			options.inputPath = arg;
		}
		else
		{
			return usageError("unexpected argument '" + arg + "'");
		}
	}

	std::unique_ptr<pcpp::conformance::Backend> backend = pcpp::conformance::createBackend(options.backendName);
	if (!backend)
	{
		return usageError("unknown backend '" + options.backendName + "'");
	}

	if (operation == "read")
	{
		return runRead(*backend, options);
	}
	return operation == "write" ? runWrite(*backend, options) : runAppend(*backend, options);
}
