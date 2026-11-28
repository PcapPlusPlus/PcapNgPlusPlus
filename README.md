# PcapNgPlusPlus

[![Coverage](https://codecov.io/gh/PcapPlusPlus/PcapNgPlusPlus/branch/main/graph/badge.svg)](https://codecov.io/gh/PcapPlusPlus/PcapNgPlusPlus)

PcapNgPlusPlus is a modern C++14 implementation of a pcapng reader and writer, intended to replace [LightPcapNg](https://github.com/rvelea/LightPcapNg) in [PcapPlusPlus](https://github.com/seladb/PcapPlusPlus). It reads, writes and appends pcapng files, including zstd-compressed ones.

> **Status:** early development (milestone M1). Nothing here is usable as a library yet. See [`docs/PLAN.md`](docs/PLAN.md) for the plan and progress.

## Why a rewrite

LightPcapNg is written in C and has accumulated bugs, edge cases and local patches in PcapPlusPlus. A rewrite is only safe if it provably behaves the same, so this project builds the test suite first and the new implementation second.

## What's in this repo

| Path | What |
| --- | --- |
| `legacy/` | A read-only copy of LightPcapNg as patched by PcapPlusPlus, pinned to a PcapPlusPlus commit. It is the reference implementation. |
| `src/`, `include/` | The new C++14 implementation. |
| `conformance/` | A test suite that runs both implementations on the same inputs and compares the results. |
| `bench/`, `fuzz/` | Benchmarks and a differential fuzzer covering both implementations. |

## How conformance is checked

- **Inputs:** a corpus generated from the pcapng spec (every block type and option, with malformed variants), real-world captures, and files found by fuzzing.
- **Oracle:** golden outputs recorded from the legacy implementation. The new implementation must match them, except for intentional fixes listed in `conformance/divergences.yaml`.
- **Memory:** no leaks or sanitizer reports, and peak memory and allocations per packet no higher than legacy's.
- **Performance:** throughput at least that of legacy on every benchmark.

Details are in [`docs/PLAN.md`](docs/PLAN.md).

## Building

```bash
cmake -S . -B build          # add -DLIGHT_PCAPNG_ZSTD=ON for zstd support
cmake --build build
```

Only the legacy LightPcapNg library builds for now.

## Contributing

Read [`AGENTS.md`](AGENTS.md) before contributing. It covers the repo rules (for example, `legacy/` and golden files are never edited by hand) and the coding conventions, which follow PcapPlusPlus.

## License

MIT. See [`LICENSE`](LICENSE). The copy of LightPcapNg in `legacy/` keeps its original license.
