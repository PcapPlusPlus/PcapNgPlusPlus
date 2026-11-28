# Conformance suite

This directory holds the suite described in [`docs/PLAN.md`](../docs/PLAN.md): a corpus of pcapng files, goldens recorded from legacy, a tool that dumps what a backend exposes, and a pytest runner that compares the two. The corpus generator comes later.

| Path | What |
| --- | --- |
| `corpus/` | Input files. Each file is a case; its case ID is its path under `corpus/`. |
| `corpus/real_world/pcapplusplus/` | Every `.pcapng`/`.zst` file in PcapPlusPlus (see its `SOURCE.md`) |
| `cases/write/` | Write scripts. Each `.json` file is a case; its case ID is its path under `cases/write/`, without `.json`. |
| `golden/read/<case ID>/<mode>.json` | The legacy dump of each corpus file, per open mode (`default`, `all_interfaces`). Generated; never edit by hand. |
| `golden/write/<case ID>.json` | The legacy dump of each write script. Generated; never edit by hand. |
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

There are two test functions:

- `test_read` runs once per corpus file and open mode, with IDs like `test_read[real_world/pcapplusplus/Tests/Packet++Test/PacketExamples/igmp.pcapng/default]`.
- `test_write` runs once per write script, with IDs like `test_write[comments/length_255]`.

Each run:

1. runs `pcapng-conformance-tool read` or `write` in its own subprocess, with a timeout;
2. compares stdout with the golden byte for byte, and shows a diff on mismatch.

How the result is judged:

- **Crash.** A non-zero exit other than a tool error, or a signal, becomes the dump `{"crash": true}`. A crash passes only if the golden records one. The failure message shows the exit code and stderr.
- **Hang.** A run that doesn't exit within `--case-timeout` seconds becomes the dump `{"hang": true}`, so a legacy hang is recorded like a crash. When the golden already records a hang, the run gets only 3 seconds, enough to confirm it.
- **No zstd.** These cases are skipped when the tool was built without zstd:
  - `.zst` corpus files;
  - write scripts that compress or write a `.zst` name. Without zstd, legacy ignores the compression level and the reader doesn't decompress.
- **32-bit `tv_sec`.** Where `timespec::tv_sec` is 32 bits (32-bit MinGW), legacy's timestamps after January 2038 wrap around. There, a case whose golden has such a timestamp is a strict expected failure. Every other case must still pass, and the run fails if a marked case starts passing.

`test_no_stale_read_goldens` and `test_no_stale_write_goldens` fail if a golden has no case left.

| Option | Meaning |
| --- | --- |
| `--tool-path=<path>` | The tool executable (required). Use `=`: with a space and no test path, pytest takes the value for a test path. |
| `--backend=<name>` | Backend to test (default: `legacy`) |
| `--regen-golden` | Write the goldens instead of comparing, and delete stale ones. Legacy backend only; needs a Release build with zstd and a 64-bit `tv_sec`. |
| `--case-timeout=<seconds>` | Per-run timeout (default: 10) |

A golden records whatever legacy does, bugs included. For example, `pcapng-example.pcapng.zst` in `all_interfaces` mode has 0 packets, because of the rewind bug in `docs/PLAN.md`. A deliberate fix in the new code will go in `divergences.yaml`; the golden is never edited to match the fix.

## pcapng-conformance-tool

The tool runs one operation of one backend on one file and prints a canonical JSON dump of everything the backend exposed through the ext API. The pytest suite runs it once per case in a subprocess, so a crash or hang only fails that case.

```bash
build/conformance/tool/pcapng-conformance-tool read [--backend legacy] [--all-interfaces] [--output dump.json] <file>
build/conformance/tool/pcapng-conformance-tool write [--backend legacy] --script <script.json> --output-dir <dir> [--output dump.json]
build/conformance/tool/pcapng-conformance-tool info
```

- `write`:
  1. runs the script through `light_create_file_info()` (or `light_create_default_file_info()`), `light_pcapng_open_write()`, `light_write_packet()`, `light_pcapng_flush()` and `light_pcapng_close()`, writing `<dir>/<fileName>`;
  2. reads the file back with the same backend, as PcapPlusPlus would;
  3. dumps both. The script format is below.
- `info` prints how the tool was built, for the test runner: `{"formatVersion":1,"backends":["legacy"],"operations":["read","write"],"zstd":true,"timestampSecBits":64}`.

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
| `Script.cpp` | Parses write scripts |
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

## Write scripts

A write case is a JSON file in `cases/write/`. Unknown keys are an error, so a typo can't turn into a different test.

```json
{
  "description": "Packets with and without comments",
  "fileInfo": {"osDesc": "Linux", "hardwareDesc": null, "userAppDesc": "PcapPlusPlus", "fileComment": ""},
  "compressionLevel": 0,
  "fileName": "out.pcapng",
  "steps": [
    {"packet": {"linkType": 1, "timestampSec": 1700000000, "timestampNsec": 5, "data": "deadbeef", "originalLength": 60, "comment": "one"}},
    {"flush": true},
    {"packet": {"data": {"length": 9000}}}
  ]
}
```

| Key | Meaning | Default |
| --- | --- | --- |
| `description` | What the case tests, for people | |
| `fileInfo` | `"default"` for `light_create_default_file_info()`, or an object with `osDesc`, `hardwareDesc`, `userAppDesc` and `fileComment` for `light_create_file_info()`. A missing or `null` string is passed as a null pointer. | `"default"` |
| `compressionLevel` | Passed to `light_pcapng_open_write()` | 0 |
| `fileName` | The output file, relative to `--output-dir`. A name containing `.zst` is read back with decompression. | `out.pcapng`, or `out.pcapng.zst` if `compressionLevel` > 0 |
| `steps` | `{"packet": {...}}` calls `light_write_packet()`; `{"flush": true}` calls `light_pcapng_flush()` | `[]` |

The packet header is filled the way PcapPlusPlus's `PcapNgFileWriterDevice::writePacket()` fills it. In particular, `comment_length` is the comment's length cast to `uint16_t`, and an empty comment is a null pointer.

| Packet key | Meaning | Default |
| --- | --- | --- |
| `linkType` | `data_link` | 1 |
| `interfaceId` | `interface_id`; PcapPlusPlus always passes 0, and the writer picks the interface by link type anyway | 0 |
| `timestampSec`, `timestampNsec` | `timestamp` | 0 |
| `data` | Hex, or `{"length": n}` for the bytes 0, 1, ..., 255, 0, 1, ... | empty |
| `capturedLength` | `captured_length`; data shorter than this is padded with zeros | the data's length |
| `originalLength` | `original_length` | `capturedLength` |
| `comment` | The packet comment | null |

Strings (file info and comments) use the dump's convention: code point U+00NN is byte NN, so `"\u00c3\u00a9"` is the UTF-8 bytes of `é`. For long values, use `{"repeat": "ab", "times": 1000}`.

### Write dump

```json
{
  "formatVersion": 1,
  "operation": "write",
  "opened": true,
  "file": {"compressed": false, "size": 524, "sha256": "826c..."},
  "reread": { ...the fields of a read dump, from readAllInterfaces to interfacesAfterRead... }
}
```

| Field | Meaning |
| --- | --- |
| `opened` | False if `light_pcapng_open_write()` returned null |
| `file` | Null if no file was created. For an uncompressed file: its size and sha256, so the bytes themselves are compared. For a compressed file, both are null: they depend on the zstd version, which differs between platforms, and `reread` still checks the content. |
| `reread` | The written file read back with `light_pcapng_open_read()` in default mode, as PcapPlusPlus would; null if there is no file |
