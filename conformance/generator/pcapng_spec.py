"""Block types and option codes from the pcapng spec (draft-ietf-opsawg-pcapng), plus LightPcapNg's own block.

Only the blocks M1 generates are listed in full: SHB, IDB, EPB and SPB. The rest are added with their case families.
"""

# Block types
SHB = 0x0A0D0D0A  # Section Header Block
IDB = 0x00000001  # Interface Description Block
SPB = 0x00000003  # Simple Packet Block
EPB = 0x00000006  # Enhanced Packet Block
LIGHT_CUSTOM_BLOCK = 0xB16B00B5  # LightPcapNg-specific custom block

BYTE_ORDER_MAGIC = 0x1A2B3C4D

# Options every block may carry
OPT_ENDOFOPT = 0
OPT_COMMENT = 1
OPT_CUSTOM_STR_SAFE = 2988
OPT_CUSTOM_BYTES_SAFE = 2989
OPT_CUSTOM_STR = 19372
OPT_CUSTOM_BYTES = 19373

# SHB options
SHB_HARDWARE = 2
SHB_OS = 3
SHB_USERAPPL = 4

# IDB options
IF_NAME = 2
IF_DESCRIPTION = 3
IF_IPV4ADDR = 4
IF_IPV6ADDR = 5
IF_MACADDR = 6
IF_EUIADDR = 7
IF_SPEED = 8
IF_TSRESOL = 9
IF_TZONE = 10
IF_FILTER = 11
IF_OS = 12
IF_FCSLEN = 13
IF_TSOFFSET = 14
IF_HARDWARE = 15
IF_TXSPEED = 16
IF_RXSPEED = 17
IF_IANA_TZNAME = 18

# EPB options
EPB_FLAGS = 2
EPB_HASH = 3
EPB_DROPCOUNT = 4
EPB_PACKETID = 5
EPB_QUEUE = 6
EPB_VERDICT = 7
EPB_PROCESSID_THREADID = 8

# Common link types
LINKTYPE_NULL = 0
LINKTYPE_ETHERNET = 1
LINKTYPE_RAW = 101
LINKTYPE_LINUX_SLL = 113
LINKTYPE_USER0 = 147


def tsresol_ticks_per_second(value):
    """Ticks per second for an if_tsresol byte: below 128 it's 10^value, from 128 it's 2^(value - 128)."""
    return 10**value if value < 128 else 2 ** (value - 128)
