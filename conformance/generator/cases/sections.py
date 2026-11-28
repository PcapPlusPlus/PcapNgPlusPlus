"""Sections and byte order (Axis 2): several sections in one file, and big-endian sections, whose byte-order magic
legacy never checks."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6


def section(link_type, seed, byte_order=b.LITTLE_ENDIAN, comment=None):
    shb_options = [b.comment(comment)] if comment else []
    blocks = [
        b.shb(shb_options),
        b.idb(link_type=link_type),
        b.epb(b.packet_data(60, seed=seed), timestamp=MICROS + seed),
    ]
    return b.Section(blocks, byte_order)


@case("sections/two", "Two sections, each with one IDB and a packet on its interface 0")
def two():
    return b.File([section(spec.LINKTYPE_ETHERNET, 0, comment="first"), section(spec.LINKTYPE_RAW, 1, comment="second")])


@case("sections/three", "Three sections with different link types")
def three():
    return b.File(
        [
            section(spec.LINKTYPE_ETHERNET, 0),
            section(spec.LINKTYPE_RAW, 1),
            section(spec.LINKTYPE_LINUX_SLL, 2),
        ]
    )


@case("sections/second_without_idb", "A second section with a packet but no IDB of its own")
def second_without_idb():
    second = b.Section([b.shb(), b.epb(b.packet_data(60, seed=1), timestamp=MICROS)])
    return b.File([section(spec.LINKTYPE_ETHERNET, 0), second])


@case("sections/big_endian", "A big-endian section; legacy reads every field as little-endian")
def big_endian():
    return b.File([section(spec.LINKTYPE_ETHERNET, 0, byte_order=b.BIG_ENDIAN, comment="big endian")])


@case("sections/little_then_big_endian", "A little-endian section followed by a big-endian one")
def little_then_big_endian():
    return b.File(
        [section(spec.LINKTYPE_ETHERNET, 0), section(spec.LINKTYPE_RAW, 1, byte_order=b.BIG_ENDIAN)]
    )
