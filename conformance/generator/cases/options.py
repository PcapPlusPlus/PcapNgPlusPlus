"""Option structure (Axis 2 and the interpreted-option variants).

Legacy parses options recursively, one stack frame per option, and checks each option's length against the space
left in the block. It interprets six options: the SHB comment, hardware, OS and user app, the IDB's if_tsresol and the
EPB comment. Each of those gets the length and structure variants here; the options it ignores are covered by
test_metamorphic.py.
"""

import struct

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6
UNKNOWN_OPTION = 0x7FFF  # Not defined for any block


def shb_file(options, end_of_options=None):
    header = b.shb(options)
    header.end_of_options = end_of_options
    return b.single_section(header, b.idb(), b.epb(b.packet_data(60), timestamp=MICROS))


def idb_file(options, end_of_options=None):
    interface = b.idb(options=options)
    interface.end_of_options = end_of_options
    return b.single_section(b.shb(), interface, b.epb(b.packet_data(60), timestamp=1_700_000_000 * 10**9))


def epb_file(options, end_of_options=None):
    packet = b.epb(b.packet_data(60), timestamp=MICROS, options=options)
    packet.end_of_options = end_of_options
    return b.single_section(b.shb(), b.idb(), packet)


INTERPRETED = [
    ("shb_comment", shb_file, spec.OPT_COMMENT, b"section comment"),
    ("shb_hardware", shb_file, spec.SHB_HARDWARE, b"hardware"),
    ("shb_os", shb_file, spec.SHB_OS, b"operating system"),
    ("shb_userappl", shb_file, spec.SHB_USERAPPL, b"application"),
    ("if_tsresol", idb_file, spec.IF_TSRESOL, bytes([9])),
    ("epb_comment", epb_file, spec.OPT_COMMENT, b"packet comment"),
]

for _name, _make, _code, _value in INTERPRETED:

    @case(f"options/{_name}_without_endofopt", f"{_name} as the last option, with no opt_endofopt after it")
    def _no_end(make=_make, code=_code, value=_value):
        return make([b.Option(code, value)], end_of_options=False)

    @case(f"options/{_name}_length_too_long", f"{_name} whose length field is 1 more than the space left",
          valid=False)
    def _too_long(make=_make, code=_code, value=_value):
        # Without opt_endofopt, the option's padded value runs to the end of the options; one more byte is too many
        return make([b.Option(code, value, length=len(value) + (-len(value) % 4) + 1)], end_of_options=False)

    @case(f"options/{_name}_length_0xffff", f"{_name} with length 0xFFFF", valid=False)
    def _huge(make=_make, code=_code, value=_value):
        return make([b.Option(code, value, length=0xFFFF)])

    @case(f"options/{_name}_unpadded", f"{_name} with no padding after a value of odd length", valid=False)
    def _unpadded(make=_make, code=_code, value=_value):
        odd = value if len(value) % 2 else value + b"x"
        return make([b.Option(code, odd, padding=b""), b.Option(UNKNOWN_OPTION, b"after")])

    @case(f"options/{_name}_twice", f"{_name} twice; the spec allows a repeated comment only",
          valid=_code == spec.OPT_COMMENT)
    def _twice(make=_make, code=_code, value=_value):
        return make([b.Option(code, value), b.Option(code, value[::-1] if len(value) > 1 else bytes([6]))])

    @case(f"options/{_name}_after_unknown", f"{_name} after an option code no block defines")
    def _after_unknown(make=_make, code=_code, value=_value):
        return make([b.Option(UNKNOWN_OPTION, b"unknown"), b.Option(code, value)])


@case("options/empty_option_ends_list", "A zero-length option before shb_os; legacy stops at a zero-length option")
def empty_option_ends_list():
    return shb_file([b.Option(UNKNOWN_OPTION, b""), b.string_option(spec.SHB_OS, "after the empty option")])


@case("options/endofopt_then_junk", "opt_endofopt followed by 8 bytes of junk before the block's trailing length",
      valid=False)
def endofopt_then_junk():
    header = b.shb([b.string_option(spec.SHB_OS, "os")])
    header.trailer = b"junkjunk"
    return b.single_section(header, b.idb(), b.epb(b.packet_data(60), timestamp=MICROS))


@case("options/endofopt_with_length", "An opt_endofopt that has a length and a value, then more options", valid=False)
def endofopt_with_length():
    options = [b.Option(spec.OPT_ENDOFOPT, b"abcd"), b.string_option(spec.SHB_OS, "after endofopt")]
    return shb_file(options, end_of_options=True)


@case("options/many", "2000 custom options (code 2989) before the comment; legacy recurses once per option")
def many():
    # A custom option's value starts with a 4-byte Private Enterprise Number; 32473 is the one for examples (RFC 5612)
    custom = [b.Option(spec.OPT_CUSTOM_BYTES_SAFE, struct.pack("<I", 32473) + bytes([i & 0xFF])) for i in range(2000)]
    return epb_file(custom + [b.comment("after 2000 options")])


@case("options/on_spb", "Option bytes in an SPB, which has no options: legacy keeps them as packet data", valid=False)
def on_spb():
    packet = b.spb(b.packet_data(20))
    packet.trailer = b.comment("not an option").to_bytes(b.LITTLE_ENDIAN)
    return b.single_section(b.shb(), b.idb(), packet)


@case("options/tsresol_on_epb", "Option code 9 on an EPB, where it isn't if_tsresol")
def tsresol_on_epb():
    return epb_file([b.Option(spec.IF_TSRESOL, bytes([3]))])


@case("options/shb_codes_on_idb", "SHB option codes 2 to 4 on an IDB, where they mean other things (code 4 is "
      "if_IPv4addr, which must be 8 bytes)", valid=False)
def shb_codes_on_idb():
    options = [b.string_option(code, f"code {code}") for code in (spec.SHB_HARDWARE, spec.SHB_OS, spec.SHB_USERAPPL)]
    return idb_file(options)
