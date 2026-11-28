"""How packets map to interfaces (Axis 2): interface IDs out of range, more interfaces than legacy keeps, and IDBs
that come after packets."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6
MAX_INTERFACES = 32  # MAX_SUPPORTED_INTERFACE_BLOCKS in light_pcapng_ext.h


def packet(interface_id=0, seed=0, ticks=MICROS):
    return b.epb(b.packet_data(60, seed=seed), interface_id=interface_id, timestamp=ticks)


@case("interfaces/id_equals_count", "An EPB on interface 1 when there is only interface 0", valid=False)
def id_equals_count():
    return b.single_section(b.shb(), b.idb(), packet(0), packet(1, seed=1), packet(0, seed=2))


@case("interfaces/id_max", "An EPB on interface 0xFFFFFFFF", valid=False)
def id_max():
    return b.single_section(b.shb(), b.idb(), packet(0xFFFFFFFF))


@case("interfaces/epb_without_idb", "An EPB in a section with no IDB at all", valid=False)
def epb_without_idb():
    return b.single_section(b.shb(), packet(0))


@case("interfaces/spb_without_idb", "An SPB in a section with no IDB: legacy doesn't set its link type", valid=False)
def spb_without_idb():
    return b.single_section(b.shb(), b.spb(b.packet_data(60)))


def many_interfaces(count, packet_interfaces):
    idbs = [b.idb(link_type=spec.LINKTYPE_USER0 + (i % 16)) for i in range(count)]
    packets = [packet(i, seed=i) for i in packet_interfaces]
    return b.single_section(b.shb(), *idbs, *packets)


@case("interfaces/exactly_max", f"{MAX_INTERFACES} IDBs, legacy's maximum, with packets on the first and last")
def exactly_max():
    return many_interfaces(MAX_INTERFACES, [0, MAX_INTERFACES - 1])


@case("interfaces/max_plus_one", f"{MAX_INTERFACES + 1} IDBs; legacy drops the last, so its packets have none")
def max_plus_one():
    return many_interfaces(MAX_INTERFACES + 1, [0, MAX_INTERFACES - 1, MAX_INTERFACES])


@case("interfaces/forty", "40 IDBs, with packets on interfaces 31, 32 and 39")
def forty():
    return many_interfaces(40, [31, 32, 39])


@case("interfaces/idb_between_packets", "A second IDB between packets; the read loop picks it up")
def idb_between_packets():
    return b.single_section(
        b.shb(),
        b.idb(),
        packet(0),
        b.idb(link_type=spec.LINKTYPE_RAW, options=[b.Option(spec.IF_TSRESOL, bytes([9]))]),
        packet(1, seed=1, ticks=1_700_000_000 * 10**9),
        packet(0, seed=2),
    )


@case("interfaces/idb_after_last_packet", "An IDB after the last packet: it appears only after reading ends")
def idb_after_last_packet():
    return b.single_section(b.shb(), b.idb(), packet(0), b.idb(link_type=spec.LINKTYPE_RAW))


@case("interfaces/packet_before_its_idb", "A packet on interface 1 before IDB 1 appears", valid=False)
def packet_before_its_idb():
    return b.single_section(b.shb(), b.idb(), packet(1), b.idb(link_type=spec.LINKTYPE_RAW), packet(1, seed=1))
