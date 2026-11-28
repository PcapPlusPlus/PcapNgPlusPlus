"""Single-bit flips in every length field of a small file (M2).

Only the low 12 bits are flipped, so a length grows by at most 4 KB. Two kinds of flip are left out, because legacy's
result for them differs between platforms, so no golden can pin it down:

- a leading length smaller than the block type's fixed fields: legacy reads those fields without checking the
  length, which reads past its buffer;
- a flip after which legacy, reading on from where the damaged block left it, takes a garbage length and allocates
  close to 4 GB (see legacy_model.py).
"""

import struct

from .. import builder as b
from .. import pcapng_spec as spec
from ..legacy_model import needs_unportable_allocation
from . import case
from .truncation import base

BITS = range(12)

# The smallest leading length each block type needs for its fixed fields
MIN_LENGTH = {spec.SHB: 28, spec.IDB: 20, spec.EPB: 32, spec.SPB: 16}


def length_fields():
    """(name, offset, struct format, block type or None) for every length field in the base file."""
    fields = []
    offset = 0
    for block in base().sections[0].blocks:
        data = block.to_bytes(b.LITTLE_ENDIAN)
        kind = {spec.SHB: "shb", spec.IDB: "idb", spec.EPB: "epb", spec.SPB: "spb"}[block.type]
        fields.append((f"{kind}_length", offset + 4, "I", block.type))
        fields.append((f"{kind}_trailing_length", offset + len(data) - 4, "I", None))
        if block.type == spec.EPB:
            fields.append(("epb_captured_length", offset + 8 + 12, "I", None))
            fields.append(("epb_original_length", offset + 8 + 16, "I", None))
        if block.type == spec.SPB:
            fields.append(("spb_original_length", offset + 8, "I", None))
        if block.options:  # the first option's length field
            fixed = 8 + sum(struct.calcsize(fmt) for _, fmt, _ in block.fields) + len(block.data) + len(
                b.padding_for(len(block.data))
            )
            fields.append((f"{kind}_option_length", offset + fixed + 2, "H", None))
        offset += len(data)
    return fields


def flipped(offset, fmt, bit):
    data = bytearray(base().to_bytes())
    value = struct.unpack_from("<" + fmt, data, offset)[0] ^ (1 << bit)
    struct.pack_into("<" + fmt, data, offset, value)
    return bytes(data), value


class RawFile:
    """A file given as bytes, for cases that edit an already serialized file."""

    def __init__(self, data):
        self.data = data
        self.sections = []

    def to_bytes(self):
        return self.data

    def pcapng_bytes(self):
        return self.data


for _name, _offset, _fmt, _block_type in length_fields():
    for _bit in BITS:
        _data, _value = flipped(_offset, _fmt, _bit)
        if _block_type is not None and _value < MIN_LENGTH[_block_type]:
            continue
        if needs_unportable_allocation(_data):
            continue

        @case(f"bitflips/{_name}_bit_{_bit:02d}", f"Bit {_bit} of {_name} flipped (now {_value})", valid=False)
        def _flip(offset=_offset, fmt=_fmt, bit=_bit):
            return RawFile(flipped(offset, fmt, bit)[0])
