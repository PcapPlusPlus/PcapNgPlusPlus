"""Section Header Block: the four options legacy interprets (comment, hardware, OS, user app), and its fields."""

from .. import builder as b
from .. import pcapng_spec as spec
from . import case


def with_packet(header):
    """A file with `header` as its SHB, then one interface and one packet, so reading continues past it."""
    return b.single_section(header, b.idb(), b.epb(b.packet_data(60), timestamp=1_700_000_000_000_000))


@case("shb/no_options", "An SHB without options, an IDB and an EPB")
def no_options():
    return with_packet(b.shb())


@case("shb/only_shb", "A file that is just an SHB without options")
def only_shb():
    return b.single_section(b.shb())


STRING_OPTIONS = {
    "comment": spec.OPT_COMMENT,
    "hardware": spec.SHB_HARDWARE,
    "os": spec.SHB_OS,
    "userappl": spec.SHB_USERAPPL,
}

for _name, _code in STRING_OPTIONS.items():

    @case(f"shb/{_name}", f"An SHB with only the {_name} option")
    def _one_option(code=_code, name=_name):
        return with_packet(b.shb([b.string_option(code, f"value of {name}")]))


@case("shb/all_options", "An SHB with comment, hardware, OS and user app")
def all_options():
    return with_packet(
        b.shb(
            [
                b.comment("a section comment"),
                b.string_option(spec.SHB_HARDWARE, "x86_64"),
                b.string_option(spec.SHB_OS, "Linux 6.8"),
                b.string_option(spec.SHB_USERAPPL, "generator"),
            ]
        )
    )


for _length in range(1, 9):

    @case(f"shb/os_length_{_length}", f"An OS option of {_length} bytes, covering each padding remainder")
    def _os_length(length=_length):
        return with_packet(b.shb([b.string_option(spec.SHB_OS, "o" * length)]))


@case("shb/empty_os", "An OS option of length 0")
def empty_os():
    return with_packet(b.shb([b.string_option(spec.SHB_OS, "")]))


@case("shb/utf8", "UTF-8 text in every string option")
def utf8():
    return with_packet(
        b.shb(
            [
                b.comment("commentaire é"),
                b.string_option(spec.SHB_HARDWARE, "matériel"),
                b.string_option(spec.SHB_OS, "système ✓"),
                b.string_option(spec.SHB_USERAPPL, "日本語"),
            ]
        )
    )


@case("shb/two_comments", "Two comment options; the spec allows repeating them")
def two_comments():
    return with_packet(b.shb([b.comment("first"), b.comment("second")]))


@case("shb/long_comment", "A 1000-byte comment")
def long_comment():
    return with_packet(b.shb([b.comment("c" * 1000)]))


@case("shb/version_1_2", "Minor version 2 (the spec's version is 1.0)")
def version_1_2():
    return with_packet(b.shb(minor=2))


@case("shb/section_length_known", "A section length field with the real length instead of -1")
def section_length_known():
    rest = [b.idb(), b.epb(b.packet_data(60), timestamp=1_700_000_000_000_000)]
    length = sum(len(block.to_bytes(b.LITTLE_ENDIAN)) for block in rest)
    return b.single_section(b.shb(section_length=length), *rest)
