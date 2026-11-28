"""Deterministic generator of pcapng test files, built from the pcapng spec (draft-ietf-opsawg-pcapng).

- pcapng_spec.py: block types and option codes
- builder.py: writes blocks and options byte by byte, with every length, padding and byte order controllable
- cases/: the case definitions, one function per generated file

Run `python3 -m generator --out <dir>` from conformance/ to write every case and a manifest.json.
"""
