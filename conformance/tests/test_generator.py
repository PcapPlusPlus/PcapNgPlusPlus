"""Checks on the corpus generator itself: its output is deterministic, and every valid file it writes is read by an
independent parser (python-pcapng) exactly as the case built it. A builder bug would otherwise be recorded silently
into the goldens, since a golden records whatever legacy does with the file."""

import io
import sys

import pcapng
import pytest

from generator import builder as b
from generator import metamorphic
from generator import pcapng_spec as spec
from generator.__main__ import MANIFEST, generate
from generator.cases import all_cases

VALID_CASES = [c for c in all_cases() if c.valid]

# python-pcapng parses options recursively too, and options/many has 2000 of them
sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))


def test_generator_is_deterministic(tmp_path):
    first = generate(tmp_path / "first")
    second = generate(tmp_path / "second")
    assert [case_id for case_id, _ in first] == [case_id for case_id, _ in second]
    assert (tmp_path / "first" / MANIFEST).read_bytes() == (tmp_path / "second" / MANIFEST).read_bytes()
    for (case_id, a), (_, b) in zip(first, second):
        assert a.read_bytes() == b.read_bytes(), case_id


def expected_fields(block):
    """The fields python-pcapng exposes for a block, as {python-pcapng attribute: value}, from the built block."""
    if block.type == spec.SHB:
        return {"version": (block.field("major"), block.field("minor"))}
    if block.type == spec.IDB:
        return {"link_type": block.field("link_type"), "snaplen": block.field("snaplen")}
    if block.type == spec.EPB:
        captured = block.field("captured_length")
        return {
            "interface_id": block.field("interface_id"),
            "timestamp_high": block.field("timestamp_high"),
            "timestamp_low": block.field("timestamp_low"),
            "captured_len": captured,
            "packet_len": block.field("original_length"),
            "packet_data": block.data[:captured],
        }
    if block.type == spec.SPB:
        return {"packet_len": block.field("original_length"), "packet_data": block.data}
    return {}  # Other block types: only the type and options are compared


def raw_option_values(parsed, code):
    """The raw values of option `code` in a python-pcapng block. get_all_raw() accepts only the codes its schema defines
    for the block type; for other codes, python-pcapng keeps the raw bytes in `data`."""
    try:
        return list(parsed.options.get_all_raw(code))
    except KeyError:
        return list(parsed.options.data[code])


@pytest.mark.parametrize("case", [pytest.param(c, id=c.case_id) for c in VALID_CASES])
def test_valid_case_parses_as_built(case):
    check_parses_as_built(case.build())


# Options python-pcapng 2.1.1 can't decode: its if_IPv6addr decoder passes an int to struct.unpack()
PYTHON_PCAPNG_CANT_DECODE = {("idb", spec.IF_IPV6ADDR)}


@pytest.mark.parametrize("pair", [pytest.param(p, id=p.pair_id) for p in metamorphic.pairs()])
def test_metamorphic_variant_parses_as_built(pair):
    """The metamorphic test's files must be valid too, or a change in the dump might come from a broken file."""
    if (pair.block_name, pair.code) in PYTHON_PCAPNG_CANT_DECODE:
        pytest.skip("python-pcapng 2.1.1 can't decode this option (a bug in its decoder)")
    check_parses_as_built(pair.base)
    check_parses_as_built(pair.variant)


def check_parses_as_built(built):
    expected_blocks = [(block, section.byte_order) for section in built.sections for block in section.blocks]
    parsed_blocks = list(pcapng.FileScanner(io.BytesIO(built.pcapng_bytes())))
    assert len(parsed_blocks) == len(expected_blocks)

    for index, ((block, order), parsed) in enumerate(zip(expected_blocks, parsed_blocks)):
        where = f"block {index} ({type(parsed).__name__})"
        if isinstance(parsed, pcapng.blocks.UnknownBlock):
            # python-pcapng keeps a block it doesn't know as its type and raw body
            assert parsed.block_type == block.type, where
            assert parsed.data == block.body_bytes(order), where
            continue
        assert parsed.magic_number == block.type, where
        for name, value in expected_fields(block).items():
            assert getattr(parsed, name) == value, f"{where}: {name}"
        # Only these carry options here; hasattr() on python-pcapng's UnknownBlock recurses forever
        if block.type in (spec.SHB, spec.IDB, spec.EPB):
            expected_options = {}
            for option in block.options:
                expected_options.setdefault(option.code, []).append(option.value_bytes(order))
            parsed_codes = {code for code, values in parsed.options.data.items() if values}
            assert parsed_codes == set(expected_options), f"{where}: option codes"
            for code, values in expected_options.items():
                assert raw_option_values(parsed, code) == values, f"{where}: option {code}"


# ---- The builder's exact bytes, against layouts written out by hand from the spec ----


@pytest.mark.parametrize(
    "length, padded",
    [(0, b""), (1, b"a\0\0\0"), (2, b"aa\0\0"), (3, b"aaa\0"), (4, b"aaaa"), (5, b"aaaaa\0\0\0")],
)
def test_option_is_padded_to_4_bytes(length, padded):
    option = b.Option(spec.SHB_OS, b"a" * length)
    assert option.to_bytes(b.LITTLE_ENDIAN) == bytes([3, 0, length, 0]) + padded


def test_shb_layout():
    expected = bytes.fromhex(
        "0a0d0d0a"  # block type
        "28000000"  # block total length: 40
        "4d3c2b1a"  # byte-order magic
        "0100" "0000"  # version 1.0
        "ffffffffffffffff"  # section length -1
        "0300" "0100" "6f000000"  # option shb_os, length 1: "o" and 3 bytes of padding
        "00000000"  # opt_endofopt
        "28000000"  # block total length again
    )
    assert b.shb([b.string_option(spec.SHB_OS, "o")]).to_bytes(b.LITTLE_ENDIAN) == expected


def test_shb_big_endian():
    data = b.shb().to_bytes(b.BIG_ENDIAN)
    assert data[:4] == bytes.fromhex("0a0d0d0a")  # the type reads the same in both orders
    assert data[4:8] == bytes.fromhex("0000001c")  # 28 bytes
    assert data[8:12] == bytes.fromhex("1a2b3c4d")


def test_epb_layout():
    expected = bytes.fromhex(
        "06000000"  # block type
        "24000000"  # block total length: 36
        "02000000"  # interface ID 2
        "01000000"  # timestamp high
        "05000000"  # timestamp low
        "03000000"  # captured length 3
        "3c000000"  # original length 60
        "aabbcc00"  # 3 bytes of data and 1 byte of padding
        "24000000"
    )
    block = b.epb(bytes.fromhex("aabbcc"), interface_id=2, timestamp=(1 << 32) + 5, original_length=60)
    assert block.to_bytes(b.LITTLE_ENDIAN) == expected


def test_spb_layout():
    expected = bytes.fromhex(
        "03000000"  # block type
        "14000000"  # block total length: 20
        "05000000"  # original length 5
        "01020000"  # 2 bytes of data and 2 bytes of padding
        "14000000"
    )
    assert b.spb(bytes([1, 2]), original_length=5).to_bytes(b.LITTLE_ENDIAN) == expected


def test_length_overrides():
    block = b.Block(spec.IDB, fields=[("link_type", "H", 1), ("reserved", "H", 0), ("snaplen", "I", 0)])
    block.total_length, block.trailing_length = 13, 99
    data = block.to_bytes(b.LITTLE_ENDIAN)
    assert data[4:8] == (13).to_bytes(4, "little") and data[-4:] == (99).to_bytes(4, "little")
    option = b.Option(spec.OPT_COMMENT, b"abc", length=200, padding=b"")
    assert option.to_bytes(b.LITTLE_ENDIAN) == bytes([1, 0, 200, 0]) + b"abc"


def test_tsresol_conversion():
    assert [spec.tsresol_ticks_per_second(v) for v in (0, 6, 9, 128, 138)] == [1, 10**6, 10**9, 1, 1024]
