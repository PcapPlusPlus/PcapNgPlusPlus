"""Shared fixtures for the conformance suite: command-line options, corpus discovery and the tool wrapper."""

import json
import pathlib
import subprocess

import pytest

CONFORMANCE_DIR = pathlib.Path(__file__).resolve().parent.parent
CORPUS_DIR = CONFORMANCE_DIR / "corpus"
GOLDEN_DIR = CONFORMANCE_DIR / "golden"

# Files under corpus/ with these suffixes are cases. Legacy picks zstd by a ".zst" in the name.
CASE_SUFFIXES = (".pcapng", ".zst", ".zstd")
ZSTD_SUFFIXES = (".zst", ".zstd")

# Exit codes of pcapng-conformance-tool that mean the tool itself failed, not the backend
TOOL_ERROR_EXIT_CODES = {2: "usage error", 3: "could not write output"}

# A backend that crashes (any other non-zero exit, or a signal) gets this dump. Exit codes and signals differ between
# platforms, so they aren't part of it.
CRASH_DUMP = b'{\n  "crash": true\n}\n'


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
        "--case-timeout", type=float, default=60.0, help="seconds before a case counts as hung (default: 60)"
    )


def corpus_cases():
    """Every corpus file, as (case ID, path), in a stable order. The case ID is the path relative to corpus/."""
    paths = (p for p in CORPUS_DIR.rglob("*") if p.is_file() and p.name.endswith(CASE_SUFFIXES))
    return sorted((p.relative_to(CORPUS_DIR).as_posix(), p) for p in paths)


def is_zstd_case(case_id):
    return case_id.endswith(ZSTD_SUFFIXES)


class ToolCrashed(Exception):
    pass


class Tool:
    """Runs pcapng-conformance-tool, one subprocess per call."""

    def __init__(self, path, timeout):
        self.path = path
        self.timeout = timeout
        self.info = json.loads(self._run(["info"]).stdout)

    def _run(self, args):
        try:
            result = subprocess.run([str(self.path)] + args, capture_output=True, timeout=self.timeout)
        except subprocess.TimeoutExpired:
            pytest.fail(f"pcapng-conformance-tool {' '.join(args)} hung (no exit within {self.timeout:g}s)")
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

    def read(self, backend, path, extra_args):
        """Reads `path` and returns (dump, crash details). The dump is CRASH_DUMP if the backend crashed, and the
        details (exit code and stderr) are then set, for the failure message."""
        try:
            return self._run(["read", "--backend", backend] + extra_args + [str(path)]).stdout, None
        except ToolCrashed as crash:
            return CRASH_DUMP, str(crash)


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
    return tool
