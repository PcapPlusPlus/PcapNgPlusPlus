"""Read every corpus file with the backend under test and compare the dump with the golden recorded from legacy."""

import difflib

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


@pytest.mark.parametrize("case_id, path, mode", read_cases())
def test_read(case_id, path, mode, tool, backend, regen_golden):
    if is_zstd_case(case_id) and not tool.info["zstd"]:
        pytest.skip("tool built without zstd")

    actual, crash = tool.read(backend, path, READ_MODES[mode])
    golden = golden_path(case_id, mode)

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
