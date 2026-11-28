#include "Script.h"

#include <nlohmann/json.hpp>

#include <algorithm>
#include <limits>
#include <set>

namespace pcpp
{
	namespace conformance
	{
		namespace
		{
			using Json = nlohmann::json;

			void checkKeys(const Json& object, const std::set<std::string>& allowed, const std::string& where)
			{
				if (!object.is_object())
				{
					throw ScriptError(where + " must be an object");
				}
				for (auto it = object.begin(); it != object.end(); ++it)
				{
					if (allowed.count(it.key()) == 0)
					{
						throw ScriptError("unknown key '" + it.key() + "' in " + where);
					}
				}
			}

			template <typename T>
			T getInteger(const Json& object, const std::string& key, T fallback, const std::string& where)
			{
				if (!object.contains(key))
				{
					return fallback;
				}
				const Json& value = object.at(key);
				if (!value.is_number_integer())
				{
					throw ScriptError(where + "." + key + " must be an integer");
				}
				if (value.is_number_unsigned())
				{
					auto number = value.get<uint64_t>();
					if (number > static_cast<uint64_t>(std::numeric_limits<T>::max()))
					{
						throw ScriptError(where + "." + key + " is out of range");
					}
					return static_cast<T>(number);
				}
				auto number = value.get<int64_t>();
				if (number < static_cast<int64_t>(std::numeric_limits<T>::min()) ||
				    (number > 0 &&
				     static_cast<uint64_t>(number) > static_cast<uint64_t>(std::numeric_limits<T>::max())))
				{
					throw ScriptError(where + "." + key + " is out of range");
				}
				return static_cast<T>(number);
			}

			/// A JSON string as bytes: code point U+00NN is byte NN, the same convention as the dump. Code points
			/// above U+00FF aren't bytes, so they are an error.
			std::string decodeByteString(const std::string& utf8, const std::string& where)
			{
				std::string bytes;
				for (size_t i = 0; i < utf8.size(); ++i)
				{
					unsigned char lead = static_cast<unsigned char>(utf8[i]);
					if (lead < 0x80)
					{
						bytes += static_cast<char>(lead);
					}
					else if ((lead == 0xC2 || lead == 0xC3) && i + 1 < utf8.size())
					{
						unsigned char next = static_cast<unsigned char>(utf8[++i]);
						bytes += static_cast<char>(((lead & 0x03) << 6) | (next & 0x3F));
					}
					else
					{
						throw ScriptError(where + " has a character above U+00FF; write each byte as \\u00XX");
					}
				}
				return bytes;
			}

			/// Bytes: a string, or {"repeat": <string>, "times": <n>} for long values.
			std::string getBytes(const Json& value, const std::string& where)
			{
				if (value.is_string())
				{
					return decodeByteString(value.get<std::string>(), where);
				}
				checkKeys(value, { "repeat", "times" }, where);
				if (!value.contains("repeat") || !value.at("repeat").is_string())
				{
					throw ScriptError(where + ".repeat must be a string");
				}
				std::string unit = decodeByteString(value.at("repeat").get<std::string>(), where + ".repeat");
				auto times = getInteger<uint32_t>(value, "times", 1, where);
				std::string bytes;
				bytes.reserve(unit.size() * times);
				for (uint32_t i = 0; i < times; ++i)
				{
					bytes += unit;
				}
				return bytes;
			}

			OptionalBytes getOptionalBytes(const Json& object, const std::string& key, const std::string& where)
			{
				OptionalBytes result;
				if (object.contains(key) && !object.at(key).is_null())
				{
					result.present = true;
					result.value = getBytes(object.at(key), where + "." + key);
				}
				return result;
			}

			/// Packet data: lowercase or uppercase hex, or {"length": <n>} for bytes 0, 1, ..., 255, 0, 1, ...
			std::vector<uint8_t> getData(const Json& packet, const std::string& where)
			{
				std::vector<uint8_t> data;
				if (!packet.contains("data"))
				{
					return data;
				}
				const Json& value = packet.at("data");
				if (value.is_object())
				{
					checkKeys(value, { "length" }, where + ".data");
					auto length = getInteger<uint32_t>(value, "length", 0, where + ".data");
					for (uint32_t i = 0; i < length; ++i)
					{
						data.push_back(static_cast<uint8_t>(i & 0xFF));
					}
					return data;
				}
				if (!value.is_string() || value.get<std::string>().size() % 2 != 0)
				{
					throw ScriptError(where + ".data must be hex with an even number of digits, or {\"length\": n}");
				}
				const std::string hex = value.get<std::string>();
				for (size_t i = 0; i < hex.size(); i += 2)
				{
					try
					{
						data.push_back(static_cast<uint8_t>(std::stoul(hex.substr(i, 2), nullptr, 16)));
					}
					catch (const std::exception&)
					{
						throw ScriptError(where + ".data isn't valid hex");
					}
				}
				return data;
			}

			PacketToWrite getPacket(const Json& value, const std::string& where)
			{
				checkKeys(value,
				          { "interfaceId", "linkType", "timestampSec", "timestampNsec", "capturedLength",
				            "originalLength", "comment", "data" },
				          where);
				PacketToWrite packet;
				packet.interfaceId = getInteger<uint32_t>(value, "interfaceId", 0, where);
				packet.linkType = getInteger<uint16_t>(value, "linkType", 1, where);
				packet.timestampSec = getInteger<int64_t>(value, "timestampSec", 0, where);
				packet.timestampNsec = getInteger<int64_t>(value, "timestampNsec", 0, where);
				packet.comment = getOptionalBytes(value, "comment", where);
				packet.data = getData(value, where);
				packet.capturedLength =
				    getInteger<uint32_t>(value, "capturedLength", static_cast<uint32_t>(packet.data.size()), where);
				packet.originalLength = getInteger<uint32_t>(value, "originalLength", packet.capturedLength, where);
				// The backend reads capturedLength bytes, so pad short data with zeros
				packet.data.resize(std::max<size_t>(packet.data.size(), packet.capturedLength), 0);
				return packet;
			}

			std::vector<WriteStep> parseSteps(const Json& root)
			{
				std::vector<WriteStep> result;
				const Json steps = root.value("steps", Json::array());
				if (!steps.is_array())
				{
					throw ScriptError("script.steps must be an array");
				}
				for (size_t i = 0; i < steps.size(); ++i)
				{
					const std::string where = "script.steps[" + std::to_string(i) + "]";
					const Json& stepJson = steps[i];
					WriteStep step;
					if (stepJson.is_object() && stepJson.size() == 1 && stepJson.contains("packet"))
					{
						step.kind = WriteStep::Kind::Packet;
						step.packet = getPacket(stepJson.at("packet"), where + ".packet");
					}
					else if (stepJson.is_object() && stepJson.size() == 1 && stepJson.contains("flush") &&
					         stepJson.at("flush") == true)
					{
						step.kind = WriteStep::Kind::Flush;
					}
					else
					{
						throw ScriptError(where + " must be {\"packet\": {...}} or {\"flush\": true}");
					}
					result.push_back(std::move(step));
				}

				return result;
			}

			Json parseRoot(const std::string& text)
			{
				try
				{
					return Json::parse(text);
				}
				catch (const Json::parse_error& error)
				{
					throw ScriptError(std::string("not valid JSON: ") + error.what());
				}
			}
		}  // namespace

		WriteScript parseWriteScript(const std::string& text)
		{
			const Json root = parseRoot(text);
			checkKeys(root, { "description", "fileName", "fileInfo", "compressionLevel", "steps" }, "the script");
			WriteScript script;

			script.compressionLevel = getInteger<int>(root, "compressionLevel", 0, "script");

			if (root.contains("fileName"))
			{
				if (!root.at("fileName").is_string() || root.at("fileName").get<std::string>().empty())
				{
					throw ScriptError("script.fileName must be a non-empty string");
				}
				script.fileName = root.at("fileName").get<std::string>();
			}
			else
			{
				script.fileName = script.compressionLevel > 0 ? "out.pcapng.zst" : "out.pcapng";
			}

			const Json fileInfo = root.value("fileInfo", Json("default"));
			if (fileInfo.is_string() && fileInfo.get<std::string>() == "default")
			{
				script.defaultFileInfo = true;
			}
			else
			{
				checkKeys(fileInfo, { "osDesc", "hardwareDesc", "userAppDesc", "fileComment" },
				          "script.fileInfo (or \"default\")");
				script.defaultFileInfo = false;
				script.osDesc = getOptionalBytes(fileInfo, "osDesc", "script.fileInfo");
				script.hardwareDesc = getOptionalBytes(fileInfo, "hardwareDesc", "script.fileInfo");
				script.userAppDesc = getOptionalBytes(fileInfo, "userAppDesc", "script.fileInfo");
				script.fileComment = getOptionalBytes(fileInfo, "fileComment", "script.fileInfo");
			}

			script.steps = parseSteps(root);

			return script;
		}

		AppendScript parseAppendScript(const std::string& text)
		{
			const Json root = parseRoot(text);
			checkKeys(root, { "description", "steps" }, "the append script");
			AppendScript script;
			script.steps = parseSteps(root);
			return script;
		}
	}  // namespace conformance
}  // namespace pcpp
