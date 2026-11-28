#include "Dump.h"

#include "Sha256.h"

#include <nlohmann/json.hpp>

namespace pcpp
{
	namespace conformance
	{
		namespace
		{
			// Keeps keys in insertion order, which is what makes the field order fixed
			using Json = nlohmann::ordered_json;

			/// Raw bytes as a JSON string, one character per byte: byte N becomes code point U+00NN. The bytes are
			/// not necessarily valid UTF-8, which nlohmann::json requires, so they are re-encoded as the UTF-8 of
			/// those code points first. Serializing with ensure_ascii then prints every non-ASCII byte as \u00XX.
			Json bytesToJson(const std::string& bytes)
			{
				std::string utf8;
				utf8.reserve(bytes.size() * 2);
				for (char ch : bytes)
				{
					unsigned char byte = static_cast<unsigned char>(ch);
					if (byte < 0x80)
					{
						utf8 += static_cast<char>(byte);
					}
					else
					{
						utf8 += static_cast<char>(0xC0 | (byte >> 6));
						utf8 += static_cast<char>(0x80 | (byte & 0x3F));
					}
				}
				return utf8;
			}

			Json optionalToJson(const OptionalBytes& value)
			{
				return value.present ? bytesToJson(value.value) : Json(nullptr);
			}

			std::string hex(const std::vector<uint8_t>& data)
			{
				static const char* const HexDigits = "0123456789abcdef";
				std::string out;
				out.reserve(data.size() * 2);
				for (uint8_t byte : data)
				{
					out += HexDigits[byte >> 4];
					out += HexDigits[byte & 0xF];
				}
				return out;
			}

			Json interfacesToJson(const std::vector<InterfaceRecord>& interfaces)
			{
				Json array = Json::array();
				for (const InterfaceRecord& iface : interfaces)
				{
					Json entry;
					entry["linkType"] = iface.linkType;
					entry["ticksPerSecond"] = iface.ticksPerSecond;
					array.push_back(std::move(entry));
				}
				return array;
			}

			Json fileInfoToJson(const FileInfo& info)
			{
				Json json;
				json["majorVersion"] = info.majorVersion;
				json["minorVersion"] = info.minorVersion;
				json["fileComment"] = optionalToJson(info.fileComment);
				json["hardwareDesc"] = optionalToJson(info.hardwareDesc);
				json["osDesc"] = optionalToJson(info.osDesc);
				json["userAppDesc"] = optionalToJson(info.userAppDesc);
				json["interfaces"] = interfacesToJson(info.interfaces);
				return json;
			}

			Json packetToJson(const PacketRecord& packet)
			{
				Json json;
				json["interfaceId"] = packet.interfaceId;
				json["linkType"] = packet.linkType;
				json["timestampSec"] = packet.timestampSec;
				json["timestampNsec"] = packet.timestampNsec;
				json["capturedLength"] = packet.capturedLength;
				json["originalLength"] = packet.originalLength;
				json["comment"] = optionalToJson(packet.comment);
				if (!packet.hasData)
				{
					json["data"] = nullptr;
				}
				else if (packet.data.size() <= MaxHexDataLength)
				{
					json["data"] = hex(packet.data);
				}
				else
				{
					json["dataSha256"] = sha256Hex(packet.data.data(), packet.data.size());
				}
				return json;
			}

			std::string compact(const Json& value)
			{
				return value.dump(-1, ' ', true);
			}

			/// The canonical layout: objects get one key per line, and arrays get one element per line, with each
			/// element printed compactly. A packet or an interface is therefore a single line, so a golden diff
			/// points at the one that changed.
			void layout(std::string& out, const Json& value, size_t depth)
			{
				const std::string indent((depth + 1) * 2, ' ');
				const std::string closingIndent(depth * 2, ' ');

				if (value.is_object() && !value.empty())
				{
					out += "{\n";
					size_t i = 0;
					for (auto it = value.begin(); it != value.end(); ++it, ++i)
					{
						out += indent + compact(it.key()) + ": ";
						layout(out, it.value(), depth + 1);
						out += (i + 1 < value.size() ? ",\n" : "\n");
					}
					out += closingIndent + "}";
				}
				else if (value.is_array() && !value.empty())
				{
					out += "[\n";
					for (size_t i = 0; i < value.size(); ++i)
					{
						out += indent + compact(value[i]);
						out += (i + 1 < value.size() ? ",\n" : "\n");
					}
					out += closingIndent + "]";
				}
				else
				{
					out += compact(value);
				}
			}
		}  // namespace

		namespace
		{
			/// Adds the fields of a read dump to @p json
			void addReadFields(Json& json, const ReadResult& result)
			{
				json["readAllInterfaces"] = result.readAllInterfaces;
				json["opened"] = result.opened;
				json["fileInfo"] = result.hasFileInfo ? fileInfoToJson(result.fileInfo) : Json(nullptr);
				json["packetCount"] = result.packets.size();

				Json packets = Json::array();
				for (const PacketRecord& packet : result.packets)
				{
					packets.push_back(packetToJson(packet));
				}
				json["packets"] = std::move(packets);

				json["interfacesAfterRead"] =
				    result.hasFileInfo ? interfacesToJson(result.interfacesAfterRead) : Json(nullptr);
			}

			std::string render(const Json& json)
			{
				std::string out;
				layout(out, json, 0);
				out += "\n";
				return out;
			}
		}  // namespace

		std::string dumpReadResult(const ReadResult& result)
		{
			Json json;
			json["formatVersion"] = DumpFormatVersion;
			json["operation"] = "read";
			addReadFields(json, result);
			return render(json);
		}

		namespace
		{
			Json writtenFileToJson(const WrittenFile& file)
			{
				if (!file.exists)
				{
					return nullptr;
				}
				Json json;
				json["compressed"] = file.compressed;
				// A compressed file's bytes depend on the zstd version, so only uncompressed files are compared
				// byte for byte; the reread checks the content of both
				json["size"] = file.compressed ? Json(nullptr) : Json(file.size);
				json["sha256"] = file.compressed ? Json(nullptr) : Json(file.sha256);
				return json;
			}

			Json rereadToJson(const ReadResult* reread)
			{
				if (reread == nullptr)
				{
					return nullptr;
				}
				Json json;
				addReadFields(json, *reread);
				return json;
			}
		}  // namespace

		std::string dumpAppendResult(const AppendResult& result, const WrittenFile& file, const ReadResult* reread)
		{
			Json json;
			json["formatVersion"] = DumpFormatVersion;
			json["operation"] = "append";
			json["opened"] = result.opened;
			json["fileInfo"] = result.hasFileInfo ? fileInfoToJson(result.fileInfo) : Json(nullptr);
			json["file"] = writtenFileToJson(file);
			json["reread"] = rereadToJson(reread);
			return render(json);
		}

		std::string dumpWriteResult(const WriteResult& result, const WrittenFile& file, const ReadResult* reread)
		{
			Json json;
			json["formatVersion"] = DumpFormatVersion;
			json["operation"] = "write";
			json["opened"] = result.opened;
			json["file"] = writtenFileToJson(file);
			json["reread"] = rereadToJson(reread);
			return render(json);
		}
	}  // namespace conformance
}  // namespace pcpp
