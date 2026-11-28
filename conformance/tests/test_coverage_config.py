"""The coverage exclusions must match what the 11 ext functions can reach, so excluded code is never reachable and
reachable code is never excluded, for example after a legacy sync. Needs no tool."""

import sys

from conftest import CONFORMANCE_DIR

sys.path.insert(0, str(CONFORMANCE_DIR / "coverage"))
import reachability  # noqa: E402


def test_gcovr_config_matches_reachability():
    expected = reachability.gcovr_config()
    actual = reachability.GCOVR_CONFIG.read_text()
    assert actual == expected, "gcovr.cfg is out of date; run conformance/coverage/reachability.py --write-config"


def test_ext_functions_are_reachable_and_not_excluded():
    _, reached = reachability.analyze()
    files, functions = reachability.exclusions()
    assert set(reachability.ROOT_FUNCTIONS) <= reached
    assert not reached & set(functions)


def test_analysis_finds_known_unreachable_code():
    """A few functions the plan names as out of scope, so a broken parser can't empty the list unnoticed."""
    files, functions = reachability.exclusions()
    assert {"light_io.c", "light_advanced.c", "light_pcapng_cont.c"} <= set(files)
    assert {"light_ip_flow", "light_pcapng_historgram", "light_subcapture", "light_pcapng_to_string"} <= set(functions)


def test_analysis_finds_known_reachable_code():
    """Functions only reached indirectly: through the zstd function pointers, and the writer's option helpers."""
    _, reached = reachability.analyze()
    assert {"read_zstd_compressed", "get_zstd_compression_context", "light_add_option", "light_create_option"} <= reached
