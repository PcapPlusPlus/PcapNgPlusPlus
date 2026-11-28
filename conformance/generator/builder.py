"""Writes pcapng blocks and options byte by byte.

A file is a list of sections; a section is a byte order and a list of blocks. Blocks and options keep their
structure until `File.to_bytes()`, so a section's byte order applies to every number in it, and so tests can compare
what a file was meant to contain with what an independent parser reads.

Every length and padding is computed by default and can be overridden, for malformed files:

- Option: `length` (the length field), `padding` (the bytes after the value)
- Block: `total_length` / `trailing_length` (the two length fields), `end_of_options` (whether opt_endofopt is
  written after the options), `trailer` (extra bytes before the trailing length)
"""

import dataclasses
import struct
from typing import List, Optional, Tuple, Union

from . import pcapng_spec as spec

LITTLE_ENDIAN = "<"
BIG_ENDIAN = ">"


def padding_for(length):
    """Zero bytes that pad `length` bytes to a multiple of 4."""
    return b"\0" * (-length % 4)


@dataclasses.dataclass
class Option:
    code: int
    # Raw bytes, or (struct format, number) for a numeric value packed in the section's byte order
    value: Union[bytes, Tuple[str, int]] = b""
    length: Optional[int] = None  # Length field; default: the value's length
    padding: Optional[bytes] = None  # Bytes after the value; default: zeros to a multiple of 4

    def value_bytes(self, order):
        if isinstance(self.value, tuple):
            fmt, number = self.value
            return struct.pack(order + fmt, number)
        return self.value

    def to_bytes(self, order):
        value = self.value_bytes(order)
        length = len(value) if self.length is None else self.length
        padding = padding_for(len(value)) if self.padding is None else self.padding
        return struct.pack(order + "HH", self.code, length) + value + padding


def string_option(code, text):
    """An option whose value is `text` encoded as UTF-8 (or raw bytes, if bytes are given)."""
    return Option(code, text if isinstance(text, bytes) else text.encode("utf-8"))


def comment(text):
    return string_option(spec.OPT_COMMENT, text)


@dataclasses.dataclass
class Block:
    type: int
    fields: List[Tuple[str, str, int]] = dataclasses.field(default_factory=list)  # (name, struct format, number)
    data: bytes = b""  # Variable-length body after the fields, padded to 4 bytes
    options: List[Option] = dataclasses.field(default_factory=list)
    end_of_options: Optional[bool] = None  # Write opt_endofopt after the options; default: if there are any
    total_length: Optional[int] = None
    trailing_length: Optional[int] = None
    trailer: bytes = b""  # Extra bytes after the options, before the trailing length

    def body_bytes(self, order):
        out = b"".join(struct.pack(order + fmt, number) for _, fmt, number in self.fields)
        out += self.data + padding_for(len(self.data))
        for option in self.options:
            out += option.to_bytes(order)
        end = bool(self.options) if self.end_of_options is None else self.end_of_options
        if end:
            out += struct.pack(order + "HH", spec.OPT_ENDOFOPT, 0)
        return out + self.trailer

    def field(self, name):
        return next(number for field_name, _, number in self.fields if field_name == name)

    def to_bytes(self, order):
        body = self.body_bytes(order)
        length = 12 + len(body)
        total = length if self.total_length is None else self.total_length
        trailing = length if self.trailing_length is None else self.trailing_length
        return struct.pack(order + "II", self.type, total) + body + struct.pack(order + "I", trailing)


@dataclasses.dataclass
class Section:
    blocks: List[Block]
    byte_order: str = LITTLE_ENDIAN


@dataclasses.dataclass
class File:
    sections: List[Section]
    trailer: bytes = b""  # Extra bytes after the last block

    def to_bytes(self):
        out = b"".join(block.to_bytes(s.byte_order) for s in self.sections for block in s.blocks)
        return out + self.trailer


def single_section(*blocks, byte_order=LITTLE_ENDIAN):
    return File([Section(list(blocks), byte_order)])


# ---- Block constructors, with the spec's field layout ----


def shb(options=(), major=1, minor=0, section_length=-1, magic=spec.BYTE_ORDER_MAGIC):
    return Block(
        spec.SHB,
        fields=[("magic", "I", magic), ("major", "H", major), ("minor", "H", minor), ("section_length", "q", section_length)],
        options=list(options),
    )


def idb(link_type=spec.LINKTYPE_ETHERNET, snaplen=0, options=(), reserved=0):
    fields = [("link_type", "H", link_type), ("reserved", "H", reserved), ("snaplen", "I", snaplen)]
    return Block(spec.IDB, fields=fields, options=list(options))


def epb(data=b"", interface_id=0, timestamp=0, captured_length=None, original_length=None, options=()):
    """An Enhanced Packet Block. `timestamp` is in the interface's ticks."""
    captured = len(data) if captured_length is None else captured_length
    original = captured if original_length is None else original_length
    return Block(
        spec.EPB,
        fields=[
            ("interface_id", "I", interface_id),
            ("timestamp_high", "I", timestamp >> 32),
            ("timestamp_low", "I", timestamp & 0xFFFFFFFF),
            ("captured_length", "I", captured),
            ("original_length", "I", original),
        ],
        data=data,
        options=list(options),
    )


def spb(data=b"", original_length=None):
    original = len(data) if original_length is None else original_length
    return Block(spec.SPB, fields=[("original_length", "I", original)], data=data)


def packet_data(length, seed=0):
    """Deterministic packet bytes: seed, seed + 1, ... modulo 256."""
    return bytes((seed + i) & 0xFF for i in range(length))
