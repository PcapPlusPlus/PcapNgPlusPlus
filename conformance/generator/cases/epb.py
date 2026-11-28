"""Enhanced Packet Block: data lengths and padding, comments, lengths, timestamps and ignored options."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6  # A timestamp in microseconds, the default resolution


def file_with(*packets, interfaces=None):
    return b.single_section(b.shb(), *(interfaces or [b.idb()]), *packets)


@case("epb/data_lengths_0_to_8", "Packets of 0 to 8 bytes, covering every padding remainder")
def data_lengths():
    return file_with(*(b.epb(b.packet_data(n), timestamp=MICROS + n) for n in range(9)))


@case("epb/jumbo", "A 9000-byte packet")
def jumbo():
    return file_with(b.epb(b.packet_data(9000), timestamp=MICROS))


@case("epb/captured_shorter_than_original", "60 bytes captured of 1514")
def captured_shorter():
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, original_length=1514))


@case("epb/comment", "A packet comment")
def comment():
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, options=[b.comment("a packet comment")]))


@case("epb/empty_comment", "A packet comment of length 0")
def empty_comment():
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, options=[b.comment("")]))


@case("epb/two_comments", "Two packet comments; legacy reports one")
def two_comments():
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, options=[b.comment("first"), b.comment("second")]))


@case("epb/comment_after_other_options", "A comment after epb_flags and epb_dropcount")
def comment_after_other_options():
    options = [b.Option(spec.EPB_FLAGS, ("I", 0x1)), b.Option(spec.EPB_DROPCOUNT, ("Q", 7)), b.comment("third")]
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, options=options))


@case("epb/ignored_options", "Options legacy doesn't interpret: flags, hash, drop count, packet ID, queue, verdict")
def ignored_options():
    options = [
        b.Option(spec.EPB_FLAGS, ("I", 0x00000001)),
        b.Option(spec.EPB_HASH, bytes([2]) + bytes(4)),
        b.Option(spec.EPB_DROPCOUNT, ("Q", 3)),
        b.Option(spec.EPB_PACKETID, ("Q", 42)),
        b.Option(spec.EPB_QUEUE, ("I", 1)),
        b.Option(spec.EPB_VERDICT, bytes([0, 1])),
    ]
    return file_with(b.epb(b.packet_data(60), timestamp=MICROS, options=options))


@case("epb/timestamps", "Timestamps from 1 second to year 2100, at microsecond resolution")
def timestamps():
    seconds = [1, 1_000_000_000, 1_700_000_000, 2**31 - 1, 2**31, 4_102_444_800]
    return file_with(*(b.epb(b.packet_data(60), timestamp=s * 10**6 + 123_456) for s in seconds))


@case("epb/interface_1_of_2", "Packets on the second of two interfaces")
def interface_1_of_2():
    return file_with(
        b.epb(b.packet_data(60), interface_id=1, timestamp=MICROS),
        b.epb(b.packet_data(60), interface_id=0, timestamp=MICROS + 1),
        interfaces=[b.idb(link_type=spec.LINKTYPE_ETHERNET), b.idb(link_type=spec.LINKTYPE_LINUX_SLL)],
    )


@case("epb/many", "500 small packets (16 to 47 bytes)")
def many():
    return file_with(*(b.epb(b.packet_data(16 + i % 32, seed=i), timestamp=MICROS + i * 1000) for i in range(500)))
