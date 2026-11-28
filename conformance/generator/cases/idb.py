"""Interface Description Block: link types, snap lengths, if_tsresol and the options legacy ignores."""

import struct

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

# 2023-11-14 22:13:20 UTC plus a fraction, as a whole number of each resolution's ticks
SECONDS = 1_700_000_000


def packets_at(ticks_per_second):
    """Two packets 1.5 seconds apart, at the given resolution."""
    start = SECONDS * ticks_per_second + ticks_per_second // 4
    return [
        b.epb(b.packet_data(60), timestamp=start),
        b.epb(b.packet_data(60, seed=1), timestamp=start + ticks_per_second * 3 // 2),
    ]


@case("idb/no_options", "An IDB without options: microsecond resolution by default")
def no_options():
    return b.single_section(b.shb(), b.idb(), *packets_at(10**6))


for _value in [0, 3, 6, 9, 0x80 + 10, 0x80 + 20]:

    @case(f"idb/tsresol_{_value}", f"if_tsresol {_value} ({spec.tsresol_ticks_per_second(_value)} ticks per second)")
    def _tsresol(value=_value):
        tsresol = b.Option(spec.IF_TSRESOL, bytes([value]))
        return b.single_section(
            b.shb(), b.idb(options=[tsresol]), *packets_at(spec.tsresol_ticks_per_second(value))
        )


for _link_type in [spec.LINKTYPE_NULL, spec.LINKTYPE_RAW, spec.LINKTYPE_LINUX_SLL, spec.LINKTYPE_USER0, 0xFFFE]:

    @case(f"idb/link_type_{_link_type}", f"An IDB with link type {_link_type}")
    def _link(link_type=_link_type):
        return b.single_section(b.shb(), b.idb(link_type=link_type), *packets_at(10**6))


@case("idb/snaplen_64", "Snap length 64, with a packet captured at that length")
def snaplen_64():
    return b.single_section(
        b.shb(), b.idb(snaplen=64), b.epb(b.packet_data(64), timestamp=SECONDS * 10**6, original_length=1500)
    )


@case("idb/two_interfaces", "Two IDBs with different link types and resolutions, and packets on each")
def two_interfaces():
    return b.single_section(
        b.shb(),
        b.idb(link_type=spec.LINKTYPE_ETHERNET),
        b.idb(link_type=spec.LINKTYPE_RAW, options=[b.Option(spec.IF_TSRESOL, bytes([9]))]),
        b.epb(b.packet_data(60), interface_id=0, timestamp=SECONDS * 10**6),
        b.epb(b.packet_data(40), interface_id=1, timestamp=SECONDS * 10**9 + 5),
        b.epb(b.packet_data(60, seed=2), interface_id=0, timestamp=SECONDS * 10**6 + 1),
    )


@case("idb/ignored_options", "Options legacy doesn't interpret: name, description, speed, OS, fcslen and tsoffset")
def ignored_options():
    options = [
        b.string_option(spec.IF_NAME, "eth0"),
        b.string_option(spec.IF_DESCRIPTION, "first interface"),
        b.Option(spec.IF_SPEED, ("Q", 1_000_000_000)),
        b.string_option(spec.IF_OS, "Linux"),
        b.Option(spec.IF_FCSLEN, bytes([4])),
        b.Option(spec.IF_TSOFFSET, ("q", 3600)),
        b.Option(spec.IF_MACADDR, bytes.fromhex("001122334455")),
        b.Option(spec.IF_IPV4ADDR, struct.pack("4B4B", 192, 168, 0, 1, 255, 255, 255, 0)),
    ]
    return b.single_section(b.shb(), b.idb(options=options), *packets_at(10**6))


@case("idb/tsresol_after_other_options", "if_tsresol 9 after other options, not first")
def tsresol_after_other_options():
    options = [b.string_option(spec.IF_NAME, "eth0"), b.Option(spec.IF_TSRESOL, bytes([9]))]
    return b.single_section(b.shb(), b.idb(options=options), *packets_at(10**9))


@case("idb/comment", "An IDB with a comment option")
def comment():
    return b.single_section(b.shb(), b.idb(options=[b.comment("interface comment")]), *packets_at(10**6))
