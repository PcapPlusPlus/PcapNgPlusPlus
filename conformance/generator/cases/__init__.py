"""The registry of generated cases. Each case is a function returning a builder.File, registered with @case."""

import collections

Case = collections.namedtuple("Case", "case_id description valid build")

CASES = {}


def case(name, description, valid=True, suffix=".pcapng"):
    """Registers a case as `generated/<name><suffix>`. `valid`: the file follows the spec, so an independent parser
    must read exactly what the case built (its pcapng bytes, before any zstd compression). Use suffix=".pcapng.zst"
    for compressed cases: legacy decompresses a file whose name contains .zst."""

    def register(build):
        case_id = f"generated/{name}{suffix}"
        if case_id in CASES:
            raise ValueError(f"duplicate case {case_id}")
        CASES[case_id] = Case(case_id, description, valid, build)
        return build

    return register


def all_cases():
    """Every case, in case ID order."""
    from . import (  # noqa: F401  (registers the cases)
        bitflips,
        blocks,
        epb,
        idb,
        interfaces,
        options,
        sections,
        shb,
        spb,
        timestamps,
        truncation,
        zstd,
    )

    return [CASES[case_id] for case_id in sorted(CASES)]
