#include "LegacyBackend.h"

#include "light_pcapng_ext.h"

#include <cstring>

namespace pcpp
{
	namespace conformance
	{
		namespace
		{
			/// Filled into the packet header before every light_get_next_packet() call. Any field the call leaves
			/// unwritten (for example, data_link of an SPB when there is no interface) then shows up in the dump as
			/// this byte pattern, deterministically, instead of as stack garbage. PcapPlusPlus itself passes an
			/// uninitialized header.
			constexpr unsigned char UnwrittenFieldPattern = 0xA5;

			struct HandleCloser
			{
				void operator()(light_pcapng_t* handle) const
				{
					light_pcapng_close(handle);
				}
			};
			using Handle = std::unique_ptr<light_pcapng_t, HandleCloser>;

			OptionalBytes toOptionalBytes(const char* data, size_t size)
			{
				OptionalBytes result;
				if (data != nullptr)
				{
					result.present = true;
					result.value.assign(data, size);
				}
				return result;
			}

			std::vector<InterfaceRecord> toInterfaces(const light_pcapng_file_info& info)
			{
				std::vector<InterfaceRecord> interfaces;
				for (size_t i = 0; i < info.interface_block_count && i < MAX_SUPPORTED_INTERFACE_BLOCKS; ++i)
				{
					InterfaceRecord iface;
					iface.linkType = info.link_types[i];
					iface.ticksPerSecond = info.timestamp_ticks_per_second[i];
					interfaces.push_back(iface);
				}
				return interfaces;
			}

			FileInfo toFileInfo(const light_pcapng_file_info& info)
			{
				FileInfo result;
				result.majorVersion = info.major_version;
				result.minorVersion = info.minor_version;
				result.fileComment = toOptionalBytes(info.file_comment, info.file_comment_size);
				result.hardwareDesc = toOptionalBytes(info.hardware_desc, info.hardware_desc_size);
				result.osDesc = toOptionalBytes(info.os_desc, info.os_desc_size);
				result.userAppDesc = toOptionalBytes(info.user_app_desc, info.user_app_desc_size);
				result.interfaces = toInterfaces(info);
				return result;
			}

			PacketRecord toPacketRecord(const light_packet_header& header, const uint8_t* data)
			{
				PacketRecord packet;
				packet.interfaceId = header.interface_id;
				packet.capturedLength = header.captured_length;
				packet.originalLength = header.original_length;
				packet.linkType = header.data_link;
				packet.timestampSec = static_cast<int64_t>(header.timestamp.tv_sec);
				packet.timestampNsec = static_cast<int64_t>(header.timestamp.tv_nsec);
				packet.comment = toOptionalBytes(header.comment, header.comment_length);
				if (data != nullptr)
				{
					// Copies captured_length bytes, as PcapPlusPlus does
					packet.hasData = true;
					packet.data.assign(data, data + header.captured_length);
				}
				return packet;
			}
		}  // namespace

		ReadResult LegacyBackend::read(const std::string& path, bool readAllInterfaces)
		{
			ReadResult result;
			result.readAllInterfaces = readAllInterfaces;

			Handle handle(light_pcapng_open_read(path.c_str(), readAllInterfaces ? LIGHT_TRUE : LIGHT_FALSE));
			if (!handle)
			{
				return result;
			}
			result.opened = true;

			const light_pcapng_file_info* info = light_pcang_get_file_info(handle.get());
			if (info != nullptr)
			{
				result.hasFileInfo = true;
				result.fileInfo = toFileInfo(*info);
			}

			while (true)
			{
				light_packet_header header;
				std::memset(&header, UnwrittenFieldPattern, sizeof(header));
				const uint8_t* data = nullptr;
				if (light_get_next_packet(handle.get(), &header, &data) == 0)
				{
					break;
				}
				result.packets.push_back(toPacketRecord(header, data));
			}

			// The file info pointer stays owned by the handle and valid until close
			info = light_pcang_get_file_info(handle.get());
			if (info != nullptr)
			{
				result.interfacesAfterRead = toInterfaces(*info);
			}

			return result;
		}

		namespace
		{
			/// An absent string becomes a null pointer. Like PcapPlusPlus's std::string::c_str(), a present one is
			/// NUL-terminated, so legacy's strlen() stops at an embedded NUL.
			const char* toCString(const OptionalBytes& value)
			{
				return value.present ? value.value.c_str() : nullptr;
			}

			void writePacket(light_pcapng_t* handle, const PacketToWrite& packet)
			{
				// Filled the way PcapPlusPlus's PcapNgFileWriterDevice::writePacket() fills it
				light_packet_header header;
				std::memset(&header, 0, sizeof(header));
				header.interface_id = packet.interfaceId;
				header.captured_length = packet.capturedLength;
				header.original_length = packet.originalLength;
				header.timestamp.tv_sec = static_cast<decltype(header.timestamp.tv_sec)>(packet.timestampSec);
				header.timestamp.tv_nsec = static_cast<decltype(header.timestamp.tv_nsec)>(packet.timestampNsec);
				header.data_link = packet.linkType;

				std::string comment = packet.comment.value;
				if (packet.comment.present && !comment.empty())
				{
					header.comment = &comment[0];
					header.comment_length = static_cast<uint16_t>(comment.size());
				}

				light_write_packet(handle, &header, packet.data.data());
			}
		}  // namespace

		WriteResult LegacyBackend::write(const std::string& path, const WriteScript& script)
		{
			WriteResult result;

			light_pcapng_file_info* info =
			    script.defaultFileInfo
			        ? light_create_default_file_info()
			        : light_create_file_info(toCString(script.osDesc), toCString(script.hardwareDesc),
			                                 toCString(script.userAppDesc), toCString(script.fileComment));

			// On success the handle owns the file info; on failure the caller frees it, as PcapPlusPlus does
			Handle handle(light_pcapng_open_write(path.c_str(), info, script.compressionLevel));
			if (!handle)
			{
				light_free_file_info(info);
				return result;
			}
			result.opened = true;

			for (const WriteStep& step : script.steps)
			{
				if (step.kind == WriteStep::Kind::Flush)
				{
					light_pcapng_flush(handle.get());
				}
				else
				{
					writePacket(handle.get(), step.packet);
				}
			}

			return result;
		}
	}  // namespace conformance
}  // namespace pcpp
