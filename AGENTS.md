# PcapNgPlusPlus Development Guide

This file is for AI coding agents (Claude Code, Codex, Copilot, etc.) and human contributors. Read it before changing anything.

## What this repo is

PcapNgPlusPlus is a C++14 rewrite of LightPcapNg, the C pcapng library that PcapPlusPlus uses today. The goal is a drop-in replacement with the same behavior, no leaks, and no memory or performance regressions.

The repo holds three things:

| Path | What | Rules |
| --- | --- | --- |
| `legacy/` | Copy of PcapPlusPlus's `3rdParty/LightPcapNg`, the reference implementation | **Read-only.** Only `scripts/sync-legacy.sh` changes it |
| `src/`, `include/` | The new C++14 implementation | Normal development |
| `conformance/` | Generator, corpus, goldens, test tool, pytest suite | See "Conformance rules" below |

The full plan, milestones, open questions and decision log are in [`docs/PLAN.md`](docs/PLAN.md). Read it before starting any milestone work.

> The repo is at the start of milestone M1. Most paths above don't exist yet. When you add a directory, build command or test command, update this file in the same change.

## Conformance rules

These protect the suite's ability to detect regressions. Don't break them, even to make a test pass.

- **Never edit `legacy/` by hand.** To pick up a PcapPlusPlus fix, run the sync script against a PcapPlusPlus commit. It updates `legacy/UPSTREAM_COMMIT` and regenerates goldens.
- **Never edit files in `conformance/golden/` by hand.** Regenerate them from the legacy backend with `--regen-golden`, and review the diff.
- **Any intentional behavior change needs an entry in `conformance/divergences.yaml`**: case ID, GitHub issue, reason, expected dump. Don't change a golden to make the new code pass.
- **The generator must be deterministic.** No timestamps, randomness without a fixed seed, or file-system ordering in its output. Golden files depend on it.
- **Generated `.pcapng` files are not committed.** Only real-world files (license checked) and minimized regressions go in `conformance/corpus/`.
- **Legacy and new code must be able to link into one binary.** Legacy keeps its `light_*` C symbols; new code lives in the `pcpp` namespace.
- **Only the 11 functions in `light_pcapng_ext.h` are in scope.** Don't port or test unreachable legacy code (`light_advanced.c`, `light_manipulate.c`, flow, histogram, split).

## Coding conventions

Same as PcapPlusPlus:

- **C++14 only.** No C++17/20 features.
- **Namespace:** `pcpp`.
- **Naming:** classes `PascalCase`, methods `camelCase`, members `m_PascalCase`.
- **Header guards:** `#pragma once`.
- **Formatting:** `clang-format` 19.1.6. Each part (`src/`/`include/`, `conformance/`, etc.) gets its own `.clang-format` when it needs one; there is no repo-wide config. Never reformat `legacy/`.
- **Docs:** public API gets Doxygen `///` comments.
- **Memory:** RAII; no raw `new`/`delete` without clear ownership. Classes that own memory define or delete copy operations.
- **Python** (generator, pytest): standard library where possible; dependencies in `conformance/requirements.txt`.

## Building and testing

```bash
cmake -S . -B build                      # add -DLIGHT_PCAPNG_ZSTD=ON for zstd support (needs zstd >= 1.4.0)
cmake --build build
```

This builds two things:

- **The legacy library**, `light_pcapng_legacy`, an alias of legacy's `light_pcapng` OBJECT library. It builds with PcapPlusPlus's own `legacy/CMakeLists.txt`, so its sources and flags match what PcapPlusPlus ships.
- **The conformance tool**, `build/conformance/tool/pcapng-conformance-tool`. Its usage and the dump format are in [`conformance/README.md`](conformance/README.md).

The default build type is Release, as in PcapPlusPlus. Generate goldens only from a Release build, because a Debug build lets legacy's `assert()` calls abort on some malformed inputs.

There is no pytest suite yet. Once it exists, it will run with something like `cd conformance && python3 -m pytest --tool-path ../build/...`.

`conformance/.clang-format` is a copy of PcapPlusPlus's config. Format with `clang-format` 19.1.6; `pip install clang-format==19.1.6` provides it.

To sync `legacy/` with PcapPlusPlus:

```bash
scripts/sync-legacy.sh [--repo <path-or-url>] [<ref>]   # default: seladb/PcapPlusPlus master
git add -f legacy                                       # -f: some upstream files match .gitignore patterns
scripts/sync-legacy.sh --check                          # exit 1 if legacy/ differs from upstream
```

CI (`.github/workflows/build.yml`) builds on PcapPlusPlus's platform matrix: Linux (PcapPlusPlus Docker images, GCC and Intel icx), macOS (arm64 and x86_64), Visual Studio (Win32, x64, ARM64), MinGW-w64, FreeBSD and Android. zstd is on where the platform provides it. A separate job warns when `legacy/` falls behind PcapPlusPlus `master`.

## Before opening a PR

- [ ] Builds on Linux, ideally macOS and Windows too.
- [ ] Conformance suite passes; sanitizer job is clean.
- [ ] No hand edits to `legacy/` or `conformance/golden/`.
- [ ] New divergences are in `divergences.yaml` with an issue link.
- [ ] `docs/PLAN.md` updated: milestone items ticked, decisions logged.
- [ ] Code formatted with `clang-format`.
