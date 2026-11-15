"""Build minimal synthetic PDFs for extraction tests.

Fixtures are fully synthetic: they contain no student content and are
generated at test time, never stored. Text is drawn with a base-14
Helvetica font at explicit positions, outlines carry /XYZ destinations like
Typst's, and XMP declaration snippets mimic (or omit) pdfaid/pdfuaid.
"""

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    Fit,
    NameObject,
)

PAGE_WIDTH = 595.0
PAGE_HEIGHT = 842.0
MARGIN_X = 72.0
BODY_SIZE = 10.0
HEADING_SIZE = 11.0

_XMP = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about="" {declarations}/>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""

#: XMP snippets for each declaration combination.
XMP_BOTH = _XMP.format(
    declarations='xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" pdfaid:part="3" '
    'pdfaid:conformance="B" '
    'xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/" pdfuaid:part="1"'
)
XMP_PDFA_ONLY = _XMP.format(
    declarations='xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/" pdfaid:part="3" '
    'pdfaid:conformance="B"'
)
XMP_PDFUA_ONLY = _XMP.format(
    declarations='xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/" pdfuaid:part="1"'
)
XMP_NEITHER = _XMP.format(declarations="")


@dataclass
class DrawnLine:
    """A line of text to draw: content, baseline y, optional size/artifact."""

    text: str
    y: float
    x: float = MARGIN_X
    size: float = BODY_SIZE
    artifact: bool = False


@dataclass
class OutlineEntry:
    """An outline item: title, 0-based target page, destination y."""

    title: str
    page: int
    y: float


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    )


def _content_stream(lines: list[DrawnLine]) -> DecodedStreamObject:
    parts: list[str] = []
    for line in lines:
        if line.artifact:
            parts.append("/Artifact BMC")
        parts.append(
            f"BT /F1 {line.size} Tf 1 0 0 1 {line.x} {line.y} Tm "
            f"({_escape(line.text)}) Tj ET"
        )
        if line.artifact:
            parts.append("EMC")
    stream = DecodedStreamObject()
    # WinAnsiEncoding covers the Finnish characters used in fixtures.
    stream.set_data("\n".join(parts).encode("latin-1"))
    return stream


def build_pdf(
    path: Path,
    pages: list[list[DrawnLine]],
    outline: list[OutlineEntry] | None = None,
    xmp: str | None = None,
) -> Path:
    """Write a synthetic PDF with positioned text, outline, and XMP."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    font_ref = writer._add_object(font)
    page_refs = []
    for lines in pages:
        page = writer.add_blank_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        page[NameObject("/Resources")] = resources
        page[NameObject("/Contents")] = writer._add_object(_content_stream(lines))
        page_refs.append(page)

    for entry in outline or []:
        writer.add_outline_item(
            title=entry.title,
            page_number=page_refs[entry.page],
            fit=Fit.xyz(left=MARGIN_X, top=entry.y, zoom=None),
        )

    if xmp is not None:
        stream = DecodedStreamObject()
        stream.set_data(xmp.encode("utf-8"))
        stream[NameObject("/Type")] = NameObject("/Metadata")
        stream[NameObject("/Subtype")] = NameObject("/XML")
        writer._root_object[NameObject("/Metadata")] = writer._add_object(stream)

    with path.open("wb") as handle:
        writer.write(handle)
    return path
