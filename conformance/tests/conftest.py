"""Shared fixtures for the conformance suite: options, case discovery, the tool wrapper and golden comparison."""

import difflib
import json
import pathlib
import subprocess

import pytest

CONFORMANCE_DIR = pathlib.Path(__file__).resolve().parent.parent
CORPUS_DIR = CONFORMANCE_DIR / "corpus"
WRITE_CASES_DIR = CONFORMANCE_DIR / "cases" / "write"
GOLDEN_DIR = CONFORMANCE_DIR / "golden"
MAX_DIFF_LINES = 60

# Files under corpus/ with these suffixes are cases. Legacy picks zstd by a ".zst" in the name.
CASE_SUFFIXES = (".pcapng", ".zst", ".zstd")
ZSTD_SUFFIXES = (".zst", ".zstd")

# Exit codes of pcapng-conformance-tool that mean the tool itself failed, not the backend
TOOL_ERROR_EXIT_CODES = {2: "usage error", 3: "could not write output"}

# A backend that crashes (any other non-zero exit, or a signal) gets this dump. Exit codes and signals differ between
# platforms, so they aren't part of it.
CRASH_DUMP = b'{\n  "crash": true\n}\n'

# A backend that doesn't exit within --case-timeout gets this dump, so a legacy hang is recorded like a crash
HANG_DUMP = b'{\n  "hang": true\n}\n'


def pytest_addoption(parser):
    group = parser.getgroup("conformance")
    group.addoption("--tool-path", help="path to the pcapng-conformance-tool executable (required)")
    group.addoption("--backend", default="legacy", help="backend to test (default: legacy)")
    group.addoption(
        "--regen-golden",
        action="store_true",
        help="write the goldens from the legacy backend instead of comparing with them, and delete stale ones",
    )
    group.addoption(
        "--case-timeout", type=float, default=10.0, help="seconds before a case counts as hung (default: 10)"
    )


def corpus_cases():
    """Every corpus file, as (case ID, path), in a stable order. The case ID is the path relative to corpus/."""
    paths = (p for p in CORPUS_DIR.rglob("*") if p.is_file() and p.name.endswith(CASE_SUFFIXES))
    return sorted((p.relative_to(CORPUS_DIR).as_posix(), p) for p in paths)


def is_zstd_case(case_id):
    return case_id.endswith(ZSTD_SUFFIXES)


def write_cases():
    """Every write script, as (case ID, path), in a stable order. The case ID is the path under cases/write/, without
    the .json suffix."""
    paths = WRITE_CASES_DIR.rglob("*.json")
    return sorted((p.relative_to(WRITE_CASES_DIR).with_suffix("").as_posix(), p) for p in paths)


def write_case_needs_zstd(script_path):
    """Whether a write script compresses or writes a .zst name; a build without zstd can't run those faithfully."""
    script = json.loads(script_path.read_text())
    return script.get("compressionLevel", 0) > 0 or ".zst" in script.get("fileName", "")


class ToolCrashed(Exception):
    pass


class ToolHung(Exception):
    pass


class Tool:
    """Runs pcapng-conformance-tool, one subprocess per call."""

    def __init__(self, path, timeout):
        self.path = path
        self.timeout = timeout
        try:
            self.info = json.loads(self._run(["info"]).stdout)
        except (ToolCrashed, ToolHung) as error:
            pytest.exit(f"pcapng-conformance-tool info failed: {error}", 2)

    def _run(self, args, timeout=None):
        timeout = timeout or self.timeout
        try:
            result = subprocess.run([str(self.path)] + args, capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise ToolHung(f"no exit within {timeout:g}s")
        if result.returncode in TOOL_ERROR_EXIT_CODES:
            pytest.fail(
                f"pcapng-conformance-tool {' '.join(args)} failed: {TOOL_ERROR_EXIT_CODES[result.returncode]}\n"
                + result.stderr.decode(errors="replace")
            )
        if result.returncode != 0:
            raise ToolCrashed(
                f"exit code {result.returncode}\n" + result.stderr.decode(errors="replace")[-2000:]
            )
        return result

    def _dump(self, args, timeout):
        """Runs an operation and returns (dump, failure details). The dump is CRASH_DUMP if the backend crashed and
        HANG_DUMP if it hung; the details (exit code and stderr, or the timeout) are then set, for the failure message."""
        try:
            return self._run(args, timeout).stdout, None
        except ToolCrashed as crash:
            return CRASH_DUMP, f"the backend crashed: {crash}"
        except ToolHung as hang:
            return HANG_DUMP, f"the backend hung: {hang}"

    def read(self, backend, path, extra_args, timeout=None):
        return self._dump(["read", "--backend", backend] + extra_args + [str(path)], timeout)

    def write(self, backend, script_path, output_dir, timeout=None):
        args = ["write", "--backend", backend, "--script", str(script_path), "--output-dir", str(output_dir)]
        return self._dump(args, timeout)


# When the golden already records a hang, this is long enough to confirm it; normal cases finish in well under 1s
CONFIRM_HANG_TIMEOUT = 3.0


def case_timeout(golden, regen_golden):
    """The timeout for a case: short if its golden is a hang, so known hangs don't slow every run."""
    if not regen_golden and golden.is_file() and golden.read_bytes() == HANG_DUMP:
        return CONFIRM_HANG_TIMEOUT
    return None


def describe_mismatch(expected, actual):
    diff = list(
        difflib.unified_diff(expected.decode().splitlines(), actual.decode().splitlines(), "golden", "actual", lineterm="")
    )
    if len(diff) > MAX_DIFF_LINES:
        diff = diff[:MAX_DIFF_LINES] + [f"... {len(diff) - MAX_DIFF_LINES} more diff lines"]
    return "\n".join(diff)


def compare_with_golden(golden, actual, crash, regen_golden):
    """Fails the test if `actual` differs from the golden file, or writes it there with --regen-golden."""
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
            message += f"\n\n{crash}"
        pytest.fail(message, pytrace=False)


def check_no_stale_goldens(golden_dir, expected, regen_golden):
    """Fails if a golden under `golden_dir` isn't in `expected`; with --regen-golden, deletes it instead."""
    stale = sorted(p for p in golden_dir.rglob("*.json") if p not in expected)
    if regen_golden:
        for path in stale:
            path.unlink()
        for directory in sorted(golden_dir.rglob("*"), reverse=True):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        return
    assert not stale, "goldens without a case (delete them with --regen-golden):\n" + "\n".join(
        str(p.relative_to(GOLDEN_DIR.parent)) for p in stale
    )


def _timestamps(value):
    """Every "timestampSec" in a dump, at any depth."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "timestampSec":
                yield item
            else:
                yield from _timestamps(item)
    elif isinstance(value, list):
        for item in value:
            yield from _timestamps(item)


def expect_failure_if_timestamps_overflow(request, tool, golden, regen_golden):
    """The ext API returns timestamps in a timespec. Where its tv_sec is 32 bits (for example 32-bit MinGW), legacy's
    timestamps after January 2038 wrap around, so a case whose golden has such a timestamp is expected to fail there.
    strict: if one starts passing, the run fails, so the mark gets removed."""
    bits = tool.info["timestampSecBits"]
    if regen_golden or bits >= 64 or not golden.is_file():
        return
    limit = 2 ** (bits - 1)
    if any(not -limit <= sec < limit for sec in _timestamps(json.loads(golden.read_bytes()))):
        request.applymarker(
            pytest.mark.xfail(strict=True, reason=f"{bits}-bit timespec::tv_sec can't hold this case's timestamps")
        )


@pytest.fixture(scope="session")
def regen_golden(request):
    return request.config.getoption("--regen-golden")


@pytest.fixture(scope="session")
def backend(request, regen_golden):
    name = request.config.getoption("--backend")
    if regen_golden and name != "legacy":
        pytest.exit("--regen-golden records the legacy backend; it can't be combined with --backend " + name, 2)
    return name


@pytest.fixture(scope="session")
def tool(request, backend, regen_golden):
    path = request.config.getoption("--tool-path")
    if not path:
        pytest.exit("--tool-path is required: point it at the pcapng-conformance-tool executable", 2)
    path = pathlib.Path(path).resolve()
    if not path.is_file():
        pytest.exit(f"--tool-path: {path} doesn't exist", 2)

    tool = Tool(path, request.config.getoption("--case-timeout"))
    if backend not in tool.info["backends"]:
        pytest.exit(f"backend {backend!r} isn't in this tool build (it has {tool.info['backends']})", 2)
    if regen_golden and not tool.info["zstd"]:
        pytest.exit("--regen-golden needs a tool built with -DLIGHT_PCAPNG_ZSTD=ON, or .zst goldens go stale", 2)
    if regen_golden and tool.info["timestampSecBits"] < 64:
        pytest.exit("--regen-golden needs a platform with a 64-bit timespec::tv_sec, or timestamps after 2038 wrap", 2)
    return tool
