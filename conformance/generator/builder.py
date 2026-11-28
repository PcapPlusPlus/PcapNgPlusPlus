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


ZSTD_MAGIC = 0xFD2FB528
ZSTD_MAX_BLOCK = 128 * 1024


def zstd_raw_frame(data, block_size=ZSTD_MAX_BLOCK):
    """A zstd frame holding `data` uncompressed, in Raw_Blocks of `block_size` bytes (RFC 8878).

    Raw blocks need no compressor and give the same bytes with any zstd version. The frame header has no content
    size, no checksum and no dictionary; its window is 128 KB, the largest block size."""
    if not 0 < block_size <= ZSTD_MAX_BLOCK:
        raise ValueError("a zstd block holds 1 to 128 KB")
    window_descriptor = 7 << 3  # 2^(10 + 7) = 128 KB
    out = struct.pack("<IBB", ZSTD_MAGIC, 0, window_descriptor)
    chunks = [data[i : i + block_size] for i in range(0, len(data), block_size)] or [b""]
    for index, chunk in enumerate(chunks):
        last = index == len(chunks) - 1
        header = int(last) | (0 << 1) | (len(chunk) << 3)  # Last_Block, Block_Type 0 (raw), Block_Size
        out += header.to_bytes(3, "little") + chunk
    return out


@dataclasses.dataclass
class Zstd:
    """Compress a file into zstd frames: the pcapng bytes are split at `frame_splits` (offsets) into frames, and each
    frame into raw blocks of `block_size` bytes. A split or block size inside a record puts a boundary mid-record."""

    frame_splits: List[int] = dataclasses.field(default_factory=list)
    block_size: int = ZSTD_MAX_BLOCK
    truncate_at: Optional[int] = None  # Cut the compressed bytes to this many

    def compress(self, data):
        offsets = [0] + sorted(self.frame_splits) + [len(data)]
        out = b"".join(zstd_raw_frame(data[a:b], self.block_size) for a, b in zip(offsets, offsets[1:]))
        return out if self.truncate_at is None else out[: self.truncate_at]


@dataclasses.dataclass
class File:
    sections: List[Section]
    trailer: bytes = b""  # Extra bytes after the last block
    truncate_at: Optional[int] = None  # Cut the file to this many bytes (before compression)
    zstd: Optional[Zstd] = None  # Compress into zstd frames; the case ID must then end in .zst

    def pcapng_bytes(self):
        """The pcapng bytes, before any compression."""
        out = b"".join(block.to_bytes(s.byte_order) for s in self.sections for block in s.blocks)
        out += self.trailer
        return out if self.truncate_at is None else out[: self.truncate_at]

    def to_bytes(self):
        data = self.pcapng_bytes()
        return self.zstd.compress(data) if self.zstd else data


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


def light_custom_block(data=b"", length=None, reserved0=0, reserved1=0, options=()):
    """LightPcapNg's own custom block (0xB16B00B5): a data length, two reserved words, the data, then options."""
    fields = [
        ("length", "I", len(data) if length is None else length),
        ("reserved0", "I", reserved0),
        ("reserved1", "I", reserved1),
    ]
    return Block(spec.LIGHT_CUSTOM_BLOCK, fields=fields, data=data, options=list(options))


def raw_block(block_type, body=b""):
    """A block of any type with `body` as is: no fields, no padding added, no options."""
    block = Block(block_type)
    block.trailer = body
    return block


def packet_data(length, seed=0):
    """Deterministic packet bytes: seed, seed + 1, ... modulo 256."""
    return bytes((seed + i) & 0xFF for i in range(length))
