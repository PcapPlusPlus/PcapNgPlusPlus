"""Run every write script with the backend under test and compare the dump with the golden recorded from legacy.

The dump covers whether the open succeeded, the written file's size and sha256 (uncompressed files only) and a read
of the written file with the same backend.
"""

import pytest

from conftest import (
    GOLDEN_DIR,
    case_timeout,
    check_no_stale_goldens,
    compare_with_golden,
    expect_failure_if_timestamps_overflow,
    write_case_needs_zstd,
    write_cases,
)

WRITE_GOLDEN_DIR = GOLDEN_DIR / "write"


def golden_path(case_id):
    return WRITE_GOLDEN_DIR / f"{case_id}.json"


@pytest.mark.parametrize("case_id, script", [pytest.param(c, p, id=c) for c, p in write_cases()])
def test_write(case_id, script, tool, backend, regen_golden, request, tmp_path):
    if write_case_needs_zstd(script) and not tool.info["zstd"]:
        pytest.skip("tool built without zstd")

    golden = golden_path(case_id)
    expect_failure_if_timestamps_overflow(request, tool, golden, regen_golden)
    actual, crash = tool.write(backend, script, tmp_path, case_timeout(golden, regen_golden))
    compare_with_golden(golden, actual, crash, regen_golden)


def test_no_stale_write_goldens(regen_golden):
    """Every write golden belongs to a write script. With --regen-golden, stale ones are deleted instead."""
    expected = {golden_path(case_id) for case_id, _ in write_cases()}
    check_no_stale_goldens(WRITE_GOLDEN_DIR, expected, regen_golden)
