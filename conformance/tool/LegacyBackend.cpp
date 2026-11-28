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
	}  // namespace conformance
}  // namespace pcpp
