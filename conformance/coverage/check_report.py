#!/usr/bin/env python3
"""Fails if a gcovr JSON report still contains code gcovr.cfg excludes.

gcovr applies --exclude-function only with GCC 14 or newer, and silently skips it otherwise, which would put the
unreachable functions back into the coverage numbers. The coverage job runs this after gcovr to catch that.

Usage: check_report.py <coverage.json>
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import reachability  # noqa: E402


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    report = json.loads(pathlib.Path(sys.argv[1]).read_text())
    files, functions = reachability.exclusions()
    excluded = set(functions)
    problems = []
    for entry in report["files"]:
        name = pathlib.Path(entry["file"]).name
        if name in files:
            problems.append(f"{entry['file']} is excluded but in the report")
        leaked = {line.get("function_name", "").split(":")[-1] for line in entry["lines"]} & excluded
        problems += [f"{entry['file']}: excluded function {fn} is in the report" for fn in sorted(leaked)]
    if problems:
        print("\n".join(problems))
        print("gcovr needs GCC 14 or newer to apply exclude-function")
        return 1
    print(f"OK: {len(files)} files and {len(functions)} functions excluded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
