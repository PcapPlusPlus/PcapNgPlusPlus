"""A small file cut at every byte: each place a read can end early (M2)."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case


def base():
    """A short file with one block of each kind legacy reads: SHB with an option, IDB with if_tsresol, EPB with a
    comment, SPB."""
    return b.single_section(
        b.shb([b.string_option(spec.SHB_OS, "abc")]),
        b.idb(options=[b.Option(spec.IF_TSRESOL, bytes([9]))]),
        b.epb(b.packet_data(20), timestamp=1_700_000_000 * 10**9, options=[b.comment("c")]),
        b.spb(b.packet_data(6, seed=1)),
    )


BASE_LENGTH = len(base().to_bytes())

for _offset in range(BASE_LENGTH):

    @case(f"truncation/at_{_offset:03d}", f"The base file cut to {_offset} of its {BASE_LENGTH} bytes", valid=False)
    def _truncated(offset=_offset):
        built = base()
        built.truncate_at = offset
        return built
