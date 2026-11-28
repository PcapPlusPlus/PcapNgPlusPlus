"""A model of how legacy frames records, used to keep platform-dependent cases out of the corpus.

light_read_record() reads a block's type and length, then allocates and reads length - 12 bytes as a uint32_t. It
doesn't check the allocation. When a length is garbage, for example after a mismatched footer leaves the reader in
the middle of the next block, the body can be close to 4 GB:

- On 64-bit platforms the allocation succeeds, the read comes up short, and the read fails cleanly.
- On 32-bit MSVC the allocation fails, and fread() into a null pointer makes the runtime abort the process.

The outcome differs between platforms, so no golden can pin it down. Such cases aren't generated.
"""

import struct

# Bodies up to this size were allocated on every CI platform (big-endian files make legacy allocate about 670 MB)
MAX_PORTABLE_ALLOCATION = 1 << 30


def largest_body_allocation(data):
    """The largest body legacy would allocate while reading `data` record by record, as uncompressed little-endian
    pcapng. Reading continues after a mismatched footer, as legacy's reader does, and stops at a short read."""
    largest = 0
    position = 0
    while position + 8 <= len(data):
        (length,) = struct.unpack_from("<I", data, position + 4)
        body = (length - 12) & 0xFFFFFFFF
        largest = max(largest, body)
        end = position + 8 + body + 4
        if end > len(data):
            break  # the body or footer read comes up short: legacy stops
        position = end
    return largest


def needs_unportable_allocation(data):
    return largest_body_allocation(data) >= MAX_PORTABLE_ALLOCATION
