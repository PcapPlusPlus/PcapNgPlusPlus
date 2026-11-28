#!/usr/bin/env python3
"""Which legacy functions the 11 ext functions PcapPlusPlus calls can reach, from the source alone.

Reads the sources legacy/CMakeLists.txt compiles, finds every function definition, and follows calls from the 11
ext functions. A function counts as called if a reachable body mentions its name, or mentions a function-pointer
variable initialized with it. That over-approximates calls, so nothing reachable is ever reported as unreachable.

Usage:
  reachability.py                  print the unreachable files and functions
  reachability.py --write-config   rewrite conformance/coverage/gcovr.cfg from them
"""

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEGACY = ROOT / "legacy"
LEGACY_SRC = LEGACY / "LightPcapNg" / "src"
GCOVR_CONFIG = pathlib.Path(__file__).resolve().parent / "gcovr.cfg"

ROOT_FUNCTIONS = [
    "light_pcapng_open_read",
    "light_pcapng_open_write",
    "light_pcapng_open_append",
    "light_create_default_file_info",
    "light_create_file_info",
    "light_free_file_info",
    "light_pcang_get_file_info",
    "light_get_next_packet",
    "light_write_packet",
    "light_pcapng_flush",
    "light_pcapng_close",
]

COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)
# A definition starts at column 0: a return type, the name, the parameters, then an opening brace
DEFINITION = re.compile(r"^[A-Za-z_][\w \t\*]*?\b([A-Za-z_]\w*)\s*\(([^;{}()]*(?:\([^)]*\)[^;{}()]*)*)\)\s*\{", re.M)
KEYWORDS = {"if", "while", "for", "switch", "return", "sizeof"}
FUNCTION_POINTER_INIT = re.compile(r"\(\s*\*\s*(\w+)\s*\)\s*\([^)]*\)\s*=\s*&?\s*(\w+)\s*;")
IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")


def compiled_sources():
    """The .c files legacy/CMakeLists.txt puts in the light_pcapng library."""
    cmake = (LEGACY / "CMakeLists.txt").read_text()
    return sorted(LEGACY / match for match in re.findall(r"(LightPcapNg/src/\w+\.c)", cmake))


def blank_comments(text):
    return COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def strip_preprocessor_dead_code(text):
    """Blanks `#if` blocks for options the build doesn't define (USE_NULL_COMPRESSION). Keeps both branches of
    USE_Z_STD: the coverage runs build with and without zstd."""
    lines = text.split("\n")
    out, skipping = [], 0
    for line in lines:
        stripped = line.strip()
        if skipping:
            if stripped.startswith("#if"):
                skipping += 1
            elif stripped.startswith("#endif"):
                skipping -= 1
            out.append("")
            continue
        if stripped.startswith("#if defined(USE_NULL_COMPRESSION)"):
            skipping = 1
            out.append("")
            continue
        out.append(line)
    return "\n".join(out)


def functions_in(path):
    """{name: body text} for every function defined in `path`."""
    text = strip_preprocessor_dead_code(blank_comments(path.read_text(errors="replace")))
    functions = {}
    for match in DEFINITION.finditer(text):
        name = match.group(1)
        if name in KEYWORDS:
            continue
        start = match.end() - 1
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    functions[name] = text[start : index + 1]
                    break
    return functions


def analyze():
    """Returns ({file name: [function names]} of every function, set of reachable names)."""
    by_file = {}
    bodies = {}
    pointer_targets = {}
    for path in compiled_sources():
        functions = functions_in(path)
        by_file[path.name] = sorted(functions)
        for name, body in functions.items():
            if name in bodies:
                raise SystemExit(f"error: {name} is defined twice; the analysis assumes unique names")
            bodies[name] = body
        text = blank_comments(path.read_text(errors="replace"))
        for variable, target in FUNCTION_POINTER_INIT.findall(text):
            pointer_targets.setdefault(variable, set()).add(target)

    missing = [name for name in ROOT_FUNCTIONS if name not in bodies]
    if missing:
        raise SystemExit(f"error: ext functions not found in the sources: {', '.join(missing)}")

    reached = set()
    pending = list(ROOT_FUNCTIONS)
    while pending:
        name = pending.pop()
        if name in reached:
            continue
        reached.add(name)
        for identifier in set(IDENTIFIER.findall(bodies[name])):
            for callee in {identifier} | pointer_targets.get(identifier, set()):
                if callee in bodies and callee not in reached:
                    pending.append(callee)
    return by_file, reached


def exclusions():
    """(files with no reachable function, unreachable functions in the other files), both sorted."""
    by_file, reached = analyze()
    files, functions = [], []
    for file_name, names in sorted(by_file.items()):
        unreachable = [n for n in names if n not in reached]
        if names and len(unreachable) == len(names):
            files.append(file_name)
        else:
            functions.extend(unreachable)
    return files, sorted(functions)


def gcovr_config():
    files, functions = exclusions()
    lines = [
        "# Generated by conformance/coverage/reachability.py --write-config; don't edit by hand.",
        "# Coverage counts the legacy code the 11 ext functions PcapPlusPlus calls can reach. These files and",
        "# functions can't be reached, so they're left out. tests/test_coverage_config.py checks this list.",
        "",
        "# gcovr resolves these paths relative to this file's directory",
        "filter = ../../legacy/LightPcapNg/",
        "",
        "# Files with no reachable function",
    ]
    lines += [f"exclude = ../../legacy/LightPcapNg/src/{name}" for name in files]
    lines += ["", "# Unreachable functions in files that also hold reachable ones"]
    lines += [f"exclude-function = {name}" for name in functions]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write-config", action="store_true", help=f"rewrite {GCOVR_CONFIG.name}")
    args = parser.parse_args()
    if args.write_config:
        GCOVR_CONFIG.write_text(gcovr_config())
        print(f"wrote {GCOVR_CONFIG}")
        return 0
    files, functions = exclusions()
    by_file, reached = analyze()
    print(f"{len(reached)} of {sum(len(v) for v in by_file.values())} functions are reachable")
    print("Unreachable files:", ", ".join(files))
    print(f"Unreachable functions in other files ({len(functions)}):", ", ".join(functions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
