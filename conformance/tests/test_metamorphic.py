"""Options legacy ignores must not change what it reads.

For every option code legacy doesn't interpret, generator.metamorphic builds a valid base file and the same file
with that option added to one block. Reading both, in default mode, must give the same dump. No goldens are needed:
the base file is the expectation.
"""

import pytest

from generator.metamorphic import pairs

PAIRS = pairs()


@pytest.mark.parametrize("pair", [pytest.param(p, id=p.pair_id) for p in PAIRS])
def test_ignored_option_changes_nothing(pair, tool, backend, tmp_path):
    base_path = tmp_path / "base.pcapng"
    variant_path = tmp_path / "variant.pcapng"
    base_path.write_bytes(pair.base.to_bytes())
    variant_path.write_bytes(pair.variant.to_bytes())

    base, base_crash = tool.read(backend, base_path, [])
    variant, variant_crash = tool.read(backend, variant_path, [])
    assert base_crash is None and variant_crash is None, base_crash or variant_crash
    assert variant == base, "adding the option changed the dump"
