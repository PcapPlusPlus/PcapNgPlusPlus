"""Read every corpus file with the backend under test and compare the dump with the golden recorded from legacy."""

import pytest

from conftest import (
    GOLDEN_DIR,
    case_timeout,
    check_no_stale_goldens,
    compare_with_golden,
    corpus_cases,
    expect_failure_if_timestamps_overflow,
    is_zstd_case,
)

# Each corpus file is read once per open mode
READ_MODES = {
    "default": [],  # what PcapPlusPlus does
    "all_interfaces": ["--all-interfaces"],
}

READ_GOLDEN_DIR = GOLDEN_DIR / "read"


def golden_path(case_id, mode):
    return READ_GOLDEN_DIR / case_id / f"{mode}.json"


def read_cases():
    return [
        pytest.param(case_id, path, mode, id=f"{case_id}/{mode}")
        for case_id, path in corpus_cases()
        for mode in READ_MODES
    ]


@pytest.mark.parametrize("case_id, path, mode", read_cases())
def test_read(case_id, path, mode, tool, backend, regen_golden, request):
    if is_zstd_case(case_id) and not tool.info["zstd"]:
        pytest.skip("tool built without zstd")

    golden = golden_path(case_id, mode)
    expect_failure_if_timestamps_overflow(request, tool, golden, regen_golden)
    actual, crash = tool.read(backend, path, READ_MODES[mode], case_timeout(golden, regen_golden))
    compare_with_golden(golden, actual, crash, regen_golden)


def test_no_stale_read_goldens(regen_golden):
    """Every read golden belongs to a corpus case. With --regen-golden, stale ones are deleted instead."""
    expected = {golden_path(case_id, mode) for case_id, _ in corpus_cases() for mode in READ_MODES}
    check_no_stale_goldens(READ_GOLDEN_DIR, expected, regen_golden)
