"""Read every corpus file with the backend under test and compare the dump with the golden recorded from legacy."""

import difflib
import json

import pytest

from conftest import GOLDEN_DIR, corpus_cases, is_zstd_case

# Each corpus file is read once per open mode
READ_MODES = {
    "default": [],  # what PcapPlusPlus does
    "all_interfaces": ["--all-interfaces"],
}

READ_GOLDEN_DIR = GOLDEN_DIR / "read"
MAX_DIFF_LINES = 60


def golden_path(case_id, mode):
    return READ_GOLDEN_DIR / case_id / f"{mode}.json"


def read_cases():
    return [
        pytest.param(case_id, path, mode, id=f"{case_id}/{mode}")
        for case_id, path in corpus_cases()
        for mode in READ_MODES
    ]


def describe_mismatch(expected, actual):
    diff = list(
        difflib.unified_diff(
            expected.decode().splitlines(),
            actual.decode().splitlines(),
            "golden",
            "actual",
            lineterm="",
        )
    )
    if len(diff) > MAX_DIFF_LINES:
        diff = diff[:MAX_DIFF_LINES] + [f"... {len(diff) - MAX_DIFF_LINES} more diff lines"]
    return "\n".join(diff)


def has_timestamp_beyond(golden, bits):
    """Whether a read golden has a packet timestamp that doesn't fit in a signed `bits`-bit tv_sec."""
    limit = 2 ** (bits - 1)
    dump = json.loads(golden.read_bytes())
    return any(not -limit <= p["timestampSec"] < limit for p in dump.get("packets", []))


@pytest.mark.parametrize("case_id, path, mode", read_cases())
def test_read(case_id, path, mode, tool, backend, regen_golden, request):
    if is_zstd_case(case_id) and not tool.info["zstd"]:
        pytest.skip("tool built without zstd")

    golden = golden_path(case_id, mode)

    # The ext API returns timestamps in a timespec. Where its tv_sec is 32 bits (for example 32-bit MinGW), legacy's
    # timestamps after January 2038 wrap around, so only cases whose golden has such a timestamp are expected to
    # fail. strict: if one starts passing, the run fails, so the mark gets removed.
    sec_bits = tool.info["timestampSecBits"]
    if not regen_golden and sec_bits < 64 and golden.is_file() and has_timestamp_beyond(golden, sec_bits):
        request.applymarker(
            pytest.mark.xfail(strict=True, reason=f"{sec_bits}-bit timespec::tv_sec can't hold this case's timestamps")
        )

    actual, crash = tool.read(backend, path, READ_MODES[mode])

    if regen_golden:
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(actual)
        return

    if not golden.is_file():
        pytest.fail(f"no golden at {golden.relative_to(GOLDEN_DIR.parent)}; record it with --regen-golden")
    expected = golden.read_bytes()
    if actual != expected:
        message = f"dump differs from the golden:\n{describe_mismatch(expected, actual)}"
        if crash:
            message += f"\n\nthe backend crashed: {crash}"
        pytest.fail(message, pytrace=False)


def test_no_stale_read_goldens(regen_golden):
    """Every read golden belongs to a corpus case. With --regen-golden, stale ones are deleted instead."""
    expected = {golden_path(case_id, mode) for case_id, _ in corpus_cases() for mode in READ_MODES}
    stale = sorted(p for p in READ_GOLDEN_DIR.rglob("*.json") if p not in expected)

    if regen_golden:
        for path in stale:
            path.unlink()
        for directory in sorted(READ_GOLDEN_DIR.rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        return

    assert not stale, "goldens without a corpus case (delete them with --regen-golden):\n" + "\n".join(
        str(p.relative_to(GOLDEN_DIR.parent)) for p in stale
    )
