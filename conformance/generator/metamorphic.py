"""Pairs of files for the metamorphic test: a valid base file, and the same file with one option legacy doesn't
interpret added to one block. Reading both must give the same dump, so these need no goldens.

Legacy interprets six options: the SHB comment, hardware, OS and user app, the IDB's if_tsresol and the EPB comment.
Every other option code defined for SHB, IDB and EPB, and the four custom option codes, is added in turn, both
before and after the options legacy does interpret. Zero-length values are left out: legacy stops reading a block's
options at the first one (options/empty_option_ends_list covers that).
"""

import collections
import struct

from . import builder as b
from . import pcapng_spec as spec

Pair = collections.namedtuple("Pair", "pair_id block_name code base variant")

CUSTOM_CODES = [spec.OPT_CUSTOM_STR_SAFE, spec.OPT_CUSTOM_BYTES_SAFE, spec.OPT_CUSTOM_STR, spec.OPT_CUSTOM_BYTES]

UNINTERPRETED = {
    "shb": CUSTOM_CODES,
    "idb": [
        spec.IF_NAME,
        spec.IF_DESCRIPTION,
        spec.IF_IPV4ADDR,
        spec.IF_IPV6ADDR,
        spec.IF_MACADDR,
        spec.IF_EUIADDR,
        spec.IF_SPEED,
        spec.IF_TZONE,
        spec.IF_FILTER,
        spec.IF_OS,
        spec.IF_FCSLEN,
        spec.IF_TSOFFSET,
        spec.IF_HARDWARE,
        spec.IF_TXSPEED,
        spec.IF_RXSPEED,
        spec.IF_IANA_TZNAME,
    ]
    + CUSTOM_CODES,
    "epb": [
        spec.EPB_FLAGS,
        spec.EPB_HASH,
        spec.EPB_DROPCOUNT,
        spec.EPB_PACKETID,
        spec.EPB_QUEUE,
        spec.EPB_VERDICT,
        spec.EPB_PROCESSID_THREADID,
    ]
    + CUSTOM_CODES,
}

# Value sizes the spec gives these options, so the variant file stays valid
VALUE_SIZES = {
    ("idb", spec.IF_IPV4ADDR): 8,
    ("idb", spec.IF_IPV6ADDR): 17,
    ("idb", spec.IF_MACADDR): 6,
    ("idb", spec.IF_EUIADDR): 8,
    ("idb", spec.IF_SPEED): 8,
    ("idb", spec.IF_TZONE): 4,
    ("idb", spec.IF_FCSLEN): 1,
    ("idb", spec.IF_TSOFFSET): 8,
    ("idb", spec.IF_TXSPEED): 8,
    ("idb", spec.IF_RXSPEED): 8,
    ("epb", spec.EPB_FLAGS): 4,
    ("epb", spec.EPB_DROPCOUNT): 8,
    ("epb", spec.EPB_PACKETID): 8,
    ("epb", spec.EPB_QUEUE): 4,
    ("epb", spec.EPB_PROCESSID_THREADID): 8,
}


def option_value(block_name, code):
    if code in CUSTOM_CODES:
        return struct.pack("<I", 32473) + b"abc"  # Private Enterprise Number for examples (RFC 5612), then data
    if (block_name, code) in VALUE_SIZES:
        return b.packet_data(VALUE_SIZES[(block_name, code)], seed=code)
    if block_name == "epb" and code == spec.EPB_HASH:
        return bytes([2]) + b.packet_data(4)  # algorithm 2 (CRC32) and a 4-byte hash
    return b"value"  # a string option, 5 bytes so it needs padding


def base_blocks():
    return {
        "shb": b.shb([b.comment("section"), b.string_option(spec.SHB_OS, "os")]),
        "idb": b.idb(options=[b.Option(spec.IF_TSRESOL, bytes([9]))]),
        "epb": b.epb(b.packet_data(30), timestamp=1_700_000_000 * 10**9 + 7, options=[b.comment("packet")]),
    }


def to_file(blocks):
    return b.single_section(
        blocks["shb"], blocks["idb"], blocks["epb"], b.epb(b.packet_data(20, seed=1), timestamp=1_700_000_001 * 10**9)
    )


def pairs():
    """Every (pair ID, base file, variant file), in a stable order."""
    result = []
    for block_name, codes in UNINTERPRETED.items():
        for code in codes:
            for position in ("first", "last"):
                variant = base_blocks()
                option = b.Option(code, option_value(block_name, code))
                options = variant[block_name].options
                options.insert(0 if position == "first" else len(options), option)
                pair_id = f"{block_name}/{code}/{position}"
                result.append(Pair(pair_id, block_name, code, to_file(base_blocks()), to_file(variant)))
    return result
