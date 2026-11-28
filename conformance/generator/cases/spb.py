"""Simple Packet Block: data lengths, original length, and SPBs mixed with EPBs."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case


@case("spb/one", "One SPB after an IDB")
def one():
    return b.single_section(b.shb(), b.idb(), b.spb(b.packet_data(60)))


@case("spb/data_lengths_0_to_8", "SPBs of 0 to 8 bytes, covering every padding remainder")
def data_lengths():
    return b.single_section(b.shb(), b.idb(), *(b.spb(b.packet_data(n)) for n in range(9)))


@case("spb/truncated_by_snaplen", "An SPB holding 64 bytes of a 1500-byte packet, with snaplen 64")
def truncated_by_snaplen():
    return b.single_section(b.shb(), b.idb(snaplen=64), b.spb(b.packet_data(64), original_length=1500))


@case("spb/mixed_with_epb", "SPBs and EPBs interleaved")
def mixed_with_epb():
    return b.single_section(
        b.shb(),
        b.idb(link_type=spec.LINKTYPE_ETHERNET),
        b.spb(b.packet_data(60)),
        b.epb(b.packet_data(60, seed=1), timestamp=1_700_000_000 * 10**6),
        b.spb(b.packet_data(61, seed=2)),
    )


@case("spb/link_type_raw", "An SPB on a raw-IP interface")
def link_type_raw():
    return b.single_section(b.shb(), b.idb(link_type=spec.LINKTYPE_RAW), b.spb(b.packet_data(40)))
