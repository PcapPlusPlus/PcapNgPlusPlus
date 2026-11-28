"""Timestamp resolution and range (Axis 2).

- if_tsresol: legacy computes 10^n below 128 and 2^(n - 128) from 128, then stores it in a uint32_t, so large values
  overflow.
- Seconds of 0, or above MAXIMUM_PACKET_SECONDS_VALUE (UINT64_MAX / 10^9), are zeroed by the reader. Each boundary
  is written at several resolutions.
"""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case

MAXIMUM_PACKET_SECONDS = (2**64 - 1) // 10**9  # MAXIMUM_PACKET_SECONDS_VALUE in light_pcapng_ext.c
MAX_TICKS = 2**64 - 1


def file_at(tsresol, ticks_list, tsresol_bytes=None):
    """One IDB with the given if_tsresol (None: no option) and a packet at each tick value."""
    options = []
    if tsresol is not None or tsresol_bytes is not None:
        options = [b.Option(spec.IF_TSRESOL, bytes([tsresol]) if tsresol_bytes is None else tsresol_bytes)]
    packets = [b.epb(b.packet_data(16, seed=i), timestamp=ticks) for i, ticks in enumerate(ticks_list)]
    return b.single_section(b.shb(), b.idb(options=options), *packets)


def typical_ticks(ticks_per_second):
    """A few ordinary timestamps at this resolution, kept within 64 bits."""
    values = [1_700_000_000 * ticks_per_second + ticks_per_second // 3, 1, ticks_per_second, ticks_per_second + 1]
    return [v for v in values if 0 <= v <= MAX_TICKS]


# Values past the M1 family's 0, 3, 6, 9, 138 and 148: overflow of 10^n, the 2^n boundary, and the largest values
for _value in [10, 12, 19, 20, 127, 128, 159, 160, 191, 255]:

    @case(f"timestamps/tsresol_{_value}", f"if_tsresol {_value}, past what legacy's uint32_t ticks-per-second can hold")
    def _tsresol(value=_value):
        ticks = spec.tsresol_ticks_per_second(value)
        return file_at(value, typical_ticks(ticks) + [MAX_TICKS])


@case("timestamps/tsresol_zero_length", "An if_tsresol option of length 0, which also ends legacy's option list",
      valid=False)
def tsresol_zero_length():
    return file_at(None, typical_ticks(10**6), tsresol_bytes=b"")


@case("timestamps/tsresol_two_bytes", "An if_tsresol option of 2 bytes (the spec says 1); legacy reads the first",
      valid=False)
def tsresol_two_bytes():
    return file_at(None, typical_ticks(10**9), tsresol_bytes=bytes([9, 3]))


@case("timestamps/tsresol_twice", "Two if_tsresol options, 6 then 9; the spec allows only one", valid=False)
def tsresol_twice():
    options = [b.Option(spec.IF_TSRESOL, bytes([6])), b.Option(spec.IF_TSRESOL, bytes([9]))]
    return b.single_section(
        b.shb(), b.idb(options=options), *(b.epb(b.packet_data(16), timestamp=t) for t in typical_ticks(10**6))
    )


# Each boundary of the reader's seconds check, at resolutions from 1 tick per second to 2^30
for _name, _value in [("seconds", 0), ("micros", 6), ("nanos", 9), ("binary_2_10", 128 + 10), ("binary_2_30", 128 + 30)]:

    @case(f"timestamps/boundaries_{_name}", f"Seconds 0, 1, the maximum, the maximum + 1 and 2^64 - 1 ticks, "
          f"at if_tsresol {_value}")
    def _boundaries(value=_value):
        ticks_per_second = spec.tsresol_ticks_per_second(value)
        seconds = [0, 1, MAXIMUM_PACKET_SECONDS, MAXIMUM_PACKET_SECONDS + 1]
        ticks = [s * ticks_per_second for s in seconds if s * ticks_per_second <= MAX_TICKS]
        ticks += [ticks_per_second - 1, MAX_TICKS]  # just under 1 second, and the largest timestamp
        return file_at(value, ticks)
