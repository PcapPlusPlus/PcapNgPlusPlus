"""python3 -m generator --out <dir>: writes every generated case under <dir>, plus <dir>/manifest.json."""

import argparse
import hashlib
import json
import pathlib
import sys

from .cases import all_cases

MANIFEST = "manifest.json"


def generate(out_dir):
    """Writes every case to `out_dir/<case ID>` and a manifest. Returns [(case ID, path)] in case ID order."""
    out_dir = pathlib.Path(out_dir)
    manifest = {}
    written = []
    for case in all_cases():
        data = case.build().to_bytes()
        path = out_dir / case.case_id
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        manifest[case.case_id] = {
            "description": case.description,
            "valid": case.valid,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        written.append((case.case_id, path))
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=pathlib.Path, help="directory to write the cases to")
    args = parser.parse_args()
    written = generate(args.out)
    print(f"{len(written)} cases written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
