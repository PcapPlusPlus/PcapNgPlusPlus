"""Append to every corpus file with every append script, and compare the dump with the golden recorded from legacy.

light_pcapng_open_append() reads the whole file first, so appending runs the parser over the entire read corpus. The
dump covers whether the open succeeded, the file info it found, the resulting file's size and sha256, and a read of
the file afterwards.
"""

import shutil

import pytest

from conftest import (
    GOLDEN_DIR,
    append_scripts,
    case_timeout,
    check_no_stale_goldens,
    compare_with_golden,
    corpus_cases,
    expect_failure_if_timestamps_overflow,
    is_zstd_case,
    script_timestamps,
)

APPEND_GOLDEN_DIR = GOLDEN_DIR / "append"
MISSING_FILE_SCRIPT = "packets"
MISSING_FILE_GOLDEN = APPEND_GOLDEN_DIR / "missing_file.json"


def golden_path(case_id, script_name):
    return APPEND_GOLDEN_DIR / case_id / f"{script_name}.json"


def append_cases():
    return [
        pytest.param(case_id, path, name, script, id=f"{case_id}/{name}")
        for case_id, path in corpus_cases()
        for name, script in append_scripts()
    ]


@pytest.mark.parametrize("case_id, path, script_name, script", append_cases())
def test_append(case_id, path, script_name, script, tool, backend, regen_golden, request, tmp_path):
    if is_zstd_case(case_id) and not tool.info["zstd"]:
        pytest.skip("tool built without zstd")

    golden = golden_path(case_id, script_name)
    expect_failure_if_timestamps_overflow(request, tool, golden, regen_golden, script_timestamps(script))
    # Append modifies the file, so work on a copy with the same name; the name decides whether it's read as zstd
    target = tmp_path / path.name
    shutil.copyfile(path, target)
    actual, crash = tool.append(backend, script, target, case_timeout(golden, regen_golden))
    compare_with_golden(golden, actual, crash, regen_golden)


def test_append_to_missing_file(tool, backend, regen_golden, tmp_path):
    """light_pcapng_open_append() on a file that doesn't exist."""
    script = dict(append_scripts())[MISSING_FILE_SCRIPT]
    actual, crash = tool.append(backend, script, tmp_path / "missing.pcapng")
    compare_with_golden(MISSING_FILE_GOLDEN, actual, crash, regen_golden)


def test_no_stale_append_goldens(regen_golden):
    """Every append golden belongs to a case. With --regen-golden, stale ones are deleted instead."""
    expected = {golden_path(case_id, name) for case_id, _ in corpus_cases() for name, _ in append_scripts()}
    expected.add(MISSING_FILE_GOLDEN)
    check_no_stale_goldens(APPEND_GOLDEN_DIR, expected, regen_golden)
