# Conformance suite

This directory holds the suite described in [`docs/PLAN.md`](../docs/PLAN.md): a corpus of pcapng files, goldens recorded from legacy, a tool that dumps what a backend exposes, and a pytest runner that compares the two. The corpus generator comes later.

| Path | What |
| --- | --- |
| `corpus/` | Input files. Each file is a case; its case ID is its path under `corpus/`. |
| `corpus/real_world/pcapplusplus/` | Every `.pcapng`/`.zst` file in PcapPlusPlus (see its `SOURCE.md`) |
| `golden/read/<case ID>/<mode>.json` | The legacy dump of each case, per open mode (`default`, `all_interfaces`). Generated; never edit by hand. |
| `tests/` | The pytest suite |
| `tool/` | `pcapng-conformance-tool` |
| `third_party/` | Vendored code (nlohmann/json) |

## Running the suite

```bash
cmake -S . -B build -DLIGHT_PCAPNG_ZSTD=ON && cmake --build build
python3 -m pip install -r conformance/requirements.txt
cd conformance
python3 -m pytest --tool-path=../build/conformance/tool/pcapng-conformance-tool
```

`test_read` runs once per corpus file and open mode, as IDs like `test_read[real_world/pcapplusplus/Tests/Packet++Test/PacketExamples/igmp.pcapng/default]`. Each run:

1. runs `pcapng-conformance-tool read` in its own subprocess, with a timeout;
2. compares stdout with the golden byte for byte, and shows a diff on mismatch.

How the result is judged:

- **Crash.** A non-zero exit other than a tool error, or a signal, becomes the dump `{"crash": true}`. A crash passes only if the golden records one. The failure message shows the exit code and stderr.
- **Hang.** A run that doesn't exit within `--case-timeout` seconds fails the case.
- **No zstd.** `.zst` cases are skipped when the tool was built without zstd.

`test_no_stale_read_goldens` fails if a golden has no corpus case left.

| Option | Meaning |
| --- | --- |
| `--tool-path=<path>` | The tool executable (required). Use `=`: with a space and no test path, pytest takes the value for a test path. |
| `--backend=<name>` | Backend to test (default: `legacy`) |
| `--regen-golden` | Write the goldens instead of comparing, and delete stale ones. Legacy backend only; needs a Release build with zstd. |
| `--case-timeout=<seconds>` | Per-run timeout (default: 60) |

A golden records whatever legacy does, bugs included. For example, `pcapng-example.pcapng.zst` in `all_interfaces` mode has 0 packets, because of the rewind bug in `docs/PLAN.md`. A deliberate fix in the new code will go in `divergences.yaml`; the golden is never edited to match the fix.

## pcapng-conformance-tool

The tool runs one operation of one backend on one file and prints a canonical JSON dump of everything the backend exposed through the ext API. The pytest suite runs it once per case in a subprocess, so a crash or hang only fails that case.

```bash
build/conformance/tool/pcapng-conformance-tool read [--backend legacy] [--all-interfaces] [--output dump.json] <file>
build/conformance/tool/pcapng-conformance-tool info    # {"formatVersion":1,"backends":["legacy"],"zstd":true}
```

- `--backend`: only `legacy` exists for now. `NewBackend` arrives in M4.
- `--all-interfaces`: passes `read_all_interfaces = true` to `light_pcapng_open_read()`. PcapPlusPlus always passes false, but the flag is part of the API.
- Exit codes:
  - 0: a dump was produced. This includes files the backend couldn't open, because that is a result to compare.
  - 2: usage error.
  - 3: the output couldn't be written.
  - Anything else, or a signal: the backend crashed.

Build in Release, which is the default. Legacy's `assert()` calls abort a Debug build on some malformed inputs that the Release build PcapPlusPlus ships reads through.

The tool is in `tool/`:

| File | Contents |
| --- | --- |
| `Backend.h` | The backend-neutral result types and the `Backend` interface |
| `LegacyBackend.cpp` | Calls the 11 ext functions the way PcapPlusPlus does |
| `Dump.cpp` | The canonical JSON writer, using the vendored [nlohmann/json](third_party/README.md) |
| `Sha256.cpp` | Hashes large packets for the dump |

## Dump format (version 1)

The tool builds the JSON with `nlohmann::ordered_json` and prints it with a small fixed layout, so the output is byte-stable on every platform:

- keys in a fixed order;
- objects get one key per line with a two-space indent;
- each array element (a packet or an interface) is printed compactly on its own line, so a golden diff points at the one that changed;
- `\n` line endings, also on Windows, and a trailing newline.

For example, this is the dump of PcapPlusPlus's `Tests/Packet++Test/PacketExamples/QinQ_802.1_AD.pcapng`:

```json
{
  "formatVersion": 1,
  "operation": "read",
  "readAllInterfaces": false,
  "opened": true,
  "fileInfo": {
    "majorVersion": 1,
    "minorVersion": 0,
    "fileComment": null,
    "hardwareDesc": null,
    "osDesc": "64-bit Windows 7 Service Pack 1, build 7601",
    "userAppDesc": "Dumpcap 1.12.1 (v1.12.1-0-g01b65bf from master-1.12)",
    "interfaces": []
  },
  "packetCount": 1,
  "packets": [
    {"interfaceId":0,"linkType":1,"timestampSec":1430378523,"timestampNsec":814664000,"capturedLength":1500,"originalLength":1500,"comment":null,"dataSha256":"f4d1b78d11d7ad50fdd215b4e5c8d1ce1f9708516deab790da4549ed5b258c0c"}
  ],
  "interfacesAfterRead": [
    {"linkType":1,"ticksPerSecond":1000000}
  ]
}
```

`fileInfo.interfaces` is empty because the file's IDB is read only by the first `light_get_next_packet()` call, which is why `interfacesAfterRead` has it.

| Field | Meaning |
| --- | --- |
| `formatVersion` | Bumped whenever the output for the same input changes. Every golden is then regenerated. |
| `opened` | False if `light_pcapng_open_read()` returned null. `fileInfo` and `interfacesAfterRead` are then null and `packets` is empty. |
| `fileInfo` | `light_pcang_get_file_info()` right after opening, or null if the handle has none (for example, the file doesn't start with an SHB). `interfaces` lists `link_types` and `timestamp_ticks_per_second` for the first `interface_block_count` entries. |
| `packets` | One entry per successful `light_get_next_packet()` call, until it returns 0. |
| `interfacesAfterRead` | The file info's interface table after the last packet. It can differ from `fileInfo.interfaces`, because the read loop picks up interface blocks that appear between packets. |

**Strings.** The file info strings and packet comments are raw bytes with a length, not C strings, and need not be valid UTF-8. The dump writes byte N as the code point U+00NN:

- ASCII bytes follow the usual JSON escaping (`\"`, `\\`, `\n`, `\u0000` and so on);
- bytes 0x80 to 0xFF always appear as `\u0080` to `ÿ`.

Decoding the JSON string and taking each code point as one byte gives back the exact bytes, so UTF-8 text shows up as its individual bytes: `é` is `Ã©`. `null` means the API returned a null pointer, which is different from `""`.

**Packet data.** `capturedLength` bytes are read from the returned data pointer, as PcapPlusPlus does:

- 256 bytes or fewer: `data`, in lowercase hex;
- more than 256 bytes: `dataSha256` instead;
- a null data pointer: `"data": null`.

**Unwritten header fields.** Before each `light_get_next_packet()` call, the tool fills the packet header with the byte `0xA5`. A field the backend doesn't write therefore shows up as that pattern, for example `"linkType": 42405`, instead of as stack garbage. Legacy does this for an SPB's link type when no interface has been read yet. PcapPlusPlus passes an uninitialized header there.

**Not in the dump.** `light_get_next_packet()` returns 0 both at end of file and on a parse error. The API gives no way to tell the two apart, so the dump doesn't try to.
