#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <vector>

/// @file
/// The backend-neutral view of what a pcapng implementation exposes through the LightPcapNg ext API.
/// Every backend fills these structures, and Dump.h turns them into canonical JSON.

namespace pcpp
{
	namespace conformance
	{
		/// A string field that the API can leave unset (a null pointer), which is different from an empty string.
		struct OptionalBytes
		{
			bool present = false;
			std::string value;  ///< Raw bytes; not necessarily NUL-free or valid UTF-8
		};

		/// One entry of the file info's interface table.
		struct InterfaceRecord
		{
			uint16_t linkType = 0;
			uint64_t ticksPerSecond = 0;
		};

		/// The file info returned by light_pcang_get_file_info().
		struct FileInfo
		{
			uint16_t majorVersion = 0;
			uint16_t minorVersion = 0;
			OptionalBytes fileComment;
			OptionalBytes hardwareDesc;
			OptionalBytes osDesc;
			OptionalBytes userAppDesc;
			std::vector<InterfaceRecord> interfaces;
		};

		/// One packet as returned by light_get_next_packet().
		struct PacketRecord
		{
			uint32_t interfaceId = 0;
			uint32_t capturedLength = 0;
			uint32_t originalLength = 0;
			uint16_t linkType = 0;
			int64_t timestampSec = 0;
			int64_t timestampNsec = 0;
			OptionalBytes comment;
			bool hasData = false;       ///< False if the API returned a null data pointer
			std::vector<uint8_t> data;  ///< capturedLength bytes from the data pointer
		};

		/// Everything observable from opening a file for reading and reading it to the end.
		struct ReadResult
		{
			bool readAllInterfaces = false;
			bool opened = false;  ///< False if light_pcapng_open_read() returned null

			/// File info right after opening. Absent if the handle has none (for example, no leading SHB).
			bool hasFileInfo = false;
			FileInfo fileInfo;

			std::vector<PacketRecord> packets;

			/// The interface table after the last packet. It can grow while reading, because the read loop picks up
			/// interface blocks that appear between packets.
			std::vector<InterfaceRecord> interfacesAfterRead;
		};

		/// One packet a write script asks for, as PcapPlusPlus would pass it to light_write_packet().
		struct PacketToWrite
		{
			uint32_t interfaceId = 0;
			uint16_t linkType = 1;
			int64_t timestampSec = 0;
			int64_t timestampNsec = 0;
			uint32_t capturedLength = 0;
			uint32_t originalLength = 0;
			OptionalBytes comment;      ///< Passed with comment_length cast to uint16_t, as PcapPlusPlus does
			std::vector<uint8_t> data;  ///< At least capturedLength bytes
		};

		/// One step of a write script: write a packet, or flush.
		struct WriteStep
		{
			enum class Kind
			{
				Packet,
				Flush
			};
			Kind kind = Kind::Packet;
			PacketToWrite packet;
		};

		/// What to write: parsed from a write case's JSON file (see conformance/README.md).
		struct WriteScript
		{
			/// True: light_create_default_file_info(). False: light_create_file_info() with the strings below,
			/// where an absent string is passed as a null pointer.
			bool defaultFileInfo = true;
			OptionalBytes osDesc;
			OptionalBytes hardwareDesc;
			OptionalBytes userAppDesc;
			OptionalBytes fileComment;

			int compressionLevel = 0;
			std::string fileName;  ///< Output file name, relative to the output directory
			std::vector<WriteStep> steps;
		};

		/// What writing exposed. The written file itself is examined, and read back, by the tool.
		struct WriteResult
		{
			bool opened = false;  ///< False if light_pcapng_open_write() returned null
		};

		/// A pcapng implementation under test.
		class Backend
		{
		public:
			virtual ~Backend() = default;

			/// Opens @p path for reading, reads every packet, then closes it.
			/// @param[in] path File to read.
			/// @param[in] readAllInterfaces Passed to the open call; true scans the whole file for interfaces first.
			/// @return What the implementation exposed while doing so.
			virtual ReadResult read(const std::string& path, bool readAllInterfaces) = 0;

			/// Creates @p path and runs @p script on it: open for writing, run each step, close.
			/// @param[in] path File to write.
			/// @param[in] script What to write.
			/// @return Whether the file could be opened.
			virtual WriteResult write(const std::string& path, const WriteScript& script) = 0;
		};

		/// Creates the backend called @p name ("legacy"), or returns null if there is no such backend.
		std::unique_ptr<Backend> createBackend(const std::string& name);

		/// The names createBackend() accepts.
		std::vector<std::string> availableBackends();
	}  // namespace conformance
}  // namespace pcpp
