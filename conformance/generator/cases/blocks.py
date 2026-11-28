"""Block types legacy doesn't treat as packets (Axis 2), and the EPB captured-length clamp.

- Any block type without its own case in parse_by_block_type() is copied as raw bytes. Body lengths of 1 to 3 give
  block lengths of 13 to 15, which the spec forbids but legacy reads in Release builds.
- LightPcapNg's own custom block 0xB16B00B5 has its own parser: a data length (clamped to the block, PcapPlusPlus
  patch #2180), two reserved words, data and options.
- An EPB's captured length is clamped to the space in the block (PcapPlusPlus patch #2180).

Total lengths below 12, or larger than the file, aren't generated: legacy then computes a body length near 4 GB,
and whether that allocation succeeds differs between platforms.
"""

import struct

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6

OTHER_BLOCK_TYPES = {
    "obsolete_packet": 0x00000002,
    "name_resolution": 0x00000004,
    "interface_statistics": 0x00000005,
    "decryption_secrets": 0x0000000A,
    "custom": 0x00000BAD,
    "custom_do_not_copy": 0x40000BAD,
    "unassigned": 0x12345678,
}


def around(*blocks):
    """`blocks` between a packet before and a packet after, to show reading continues past them."""
    return b.single_section(
        b.shb(),
        b.idb(),
        b.epb(b.packet_data(60), timestamp=MICROS),
        *blocks,
        b.epb(b.packet_data(60, seed=1), timestamp=MICROS + 1),
    )


for _name, _type in OTHER_BLOCK_TYPES.items():

    @case(f"blocks/{_name}", f"A block of type {_type:#010x} with a 16-byte body", valid=_type in (4, 5))
    def _other(block_type=_type):
        if block_type == 4:  # A real NRB: one IPv4 record (address and name) and the end-of-records record
            record = bytes([192, 168, 0, 1]) + b"host.example\0"
            body = struct.pack("<HH", 1, len(record)) + record + b.padding_for(len(record)) + struct.pack("<HH", 0, 0)
            return around(b.raw_block(block_type, body))
        if block_type == 5:  # A real ISB: interface 0, a timestamp, no options
            return around(b.Block(block_type, fields=[("interface_id", "I", 0), ("ts_high", "I", 0),
                                                       ("ts_low", "I", 5)]))
        return around(b.raw_block(block_type, b.packet_data(16, seed=block_type & 0xFF)))


for _length in range(0, 4):

    @case(f"blocks/unknown_body_length_{_length}", f"An unknown block with a {_length}-byte body "
          f"(total length {12 + _length})", valid=False)
    def _short(length=_length):
        return around(b.raw_block(0x12345678, b.packet_data(length)))


@case("blocks/unknown_large", "An unknown block with a 64 KB body", valid=False)
def unknown_large():
    return around(b.raw_block(0x12345678, b.packet_data(65536)))


@case("blocks/light_custom", "LightPcapNg's custom block 0xB16B00B5 with data and a comment", valid=False)
def light_custom():
    return around(b.light_custom_block(b.packet_data(10), reserved0=1, reserved1=2, options=[b.comment("custom")]))


@case("blocks/light_custom_no_options", "LightPcapNg's custom block without options", valid=False)
def light_custom_no_options():
    return around(b.light_custom_block(b.packet_data(8)))


@case("blocks/light_custom_empty", "LightPcapNg's custom block with no data", valid=False)
def light_custom_empty():
    return around(b.light_custom_block(b""))


@case("blocks/light_custom_length_too_long", "LightPcapNg's custom block whose data length exceeds the block",
      valid=False)
def light_custom_length_too_long():
    return around(b.light_custom_block(b.packet_data(8), length=1000))


@case("blocks/epb_captured_beyond_block", "An EPB claiming 1000 captured bytes in a block holding 60", valid=False)
def epb_captured_beyond_block():
    return b.single_section(b.shb(), b.idb(), b.epb(b.packet_data(60), timestamp=MICROS, captured_length=1000))


@case("blocks/epb_captured_beyond_block_with_comment", "As above, but the block also has a comment, which then "
      "counts as packet data", valid=False)
def epb_captured_beyond_block_with_comment():
    packet = b.epb(b.packet_data(60), timestamp=MICROS, captured_length=1000, options=[b.comment("comment")])
    return b.single_section(b.shb(), b.idb(), packet)


@case("blocks/epb_captured_beyond_original", "Captured length 60, original length 10")
def epb_captured_beyond_original():
    return b.single_section(b.shb(), b.idb(), b.epb(b.packet_data(60), timestamp=MICROS, original_length=10))


@case("blocks/spb_original_beyond_block", "An SPB whose original length is larger than the data it holds, with "
      "no snap length to explain it", valid=False)
def spb_original_beyond_block():
    return b.single_section(b.shb(), b.idb(), b.spb(b.packet_data(60), original_length=60000))


@case("blocks/file_trailing_junk", "3 bytes of junk after the last block", valid=False)
def file_trailing_junk():
    built = around()
    built.trailer = b"\x01\x02\x03"
    return built
