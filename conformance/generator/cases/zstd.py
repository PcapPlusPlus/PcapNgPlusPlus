"""The zstd I/O layer (Axis 2): legacy decompresses a file whose name contains .zst.

The files use raw (stored) zstd blocks, so they need no compressor and are the same with any zstd version. Frame and
block boundaries are placed inside pcapng records, which exercises the reader's path for a read that spans two
decompressed chunks. Every block type the generator writes is included.
"""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MICROS = 1_700_000_000 * 10**6


def every_block_type():
    """A file with every kind of block legacy parses differently."""
    return b.single_section(
        b.shb([b.comment("compressed"), b.string_option(spec.SHB_OS, "zstd")]),
        b.idb(options=[b.Option(spec.IF_TSRESOL, bytes([6]))]),
        b.epb(b.packet_data(60), timestamp=MICROS, options=[b.comment("first")]),
        b.spb(b.packet_data(33, seed=1)),
        b.light_custom_block(b.packet_data(10)),
        b.raw_block(0x12345678, b.packet_data(16)),
        b.epb(b.packet_data(61, seed=2), timestamp=MICROS + 1),
    )


def zstd_case(name, description, **zstd_args):
    @case(f"zstd/{name}", description, suffix=".pcapng.zst")
    def build():
        built = every_block_type()
        built.zstd = b.Zstd(**zstd_args)
        return built

    return build


zstd_case("one_frame", "Every block type in one zstd frame")
zstd_case("seven_byte_blocks", "zstd blocks of 7 bytes, so every record spans several blocks", block_size=7)
zstd_case("frame_split_mid_epb", "Two zstd frames, split in the middle of the first EPB", frame_splits=[90])
zstd_case("frame_per_50_bytes", "A new zstd frame every 50 bytes", frame_splits=list(range(50, 400, 50)))
zstd_case("empty_first_frame", "An empty zstd frame before the data", frame_splits=[0])
zstd_case("truncated_frame", "The zstd stream cut in the middle of a block", truncate_at=150)


@case("zstd/large", "360 KB of packets (40 of 9000 bytes), more than legacy's decompression buffer", suffix=".pcapng.zst")
def large():
    packets = [b.epb(b.packet_data(9000, seed=i), timestamp=MICROS + i) for i in range(40)]
    built = b.single_section(b.shb(), b.idb(), *packets)
    built.zstd = b.Zstd()
    return built


@case("zstd/truncated_pcapng", "A complete zstd stream holding a pcapng file cut in the middle of an EPB",
      valid=False, suffix=".pcapng.zst")
def truncated_pcapng():
    built = every_block_type()
    built.truncate_at = 100
    built.zstd = b.Zstd()
    return built
