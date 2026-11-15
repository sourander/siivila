"""PDF submission extraction: topics, paragraphs, provenance.

Reads Typst-generated PDF submissions into an ordered hierarchy of topics
and paragraphs with source-page provenance. Approach (validated against the
local reference documents, see the add-pdf-extraction design):

- Lines are reconstructed from text-showing operators with full CTM x TM
  matrix math; chunks within a small vertical tolerance merge into one line
  in reading order (top to bottom, left to right).
- Topic boundaries come from the document outline: each entry is matched to
  its heading line on the destination page (by text, nearest to the
  destination y). Content between heading lines belongs to the preceding
  topic, so several headings can share one page.
- Paragraph breaks are vertical gaps clearly larger than the document's
  median line gap. A page boundary alone never splits a paragraph, so a
  paragraph spanning pages keeps its complete text in reading order. The
  trade-off: a new paragraph starting exactly at the top of a page merges
  into the previous one (documented, deterministic).
- Text inside /Artifact marked-content blocks (page headers, footers, page
  numbers) is excluded.
- Content before the first heading (title pages, tables of contents) is not
  part of any topic and is discarded.

Canonical text rules (explicit and deterministic): within a paragraph, lines
are joined in reading order; a line ending in a hyphen joins the next line
without a space (hyphenation), otherwise lines join with a single space;
all whitespace runs collapse to single spaces. Canonical text is exact
relative to itself, not a guarantee of visual fidelity to the PDF.

Failure reasons are safe, fixed codes and messages: they never contain
student text or exception payloads.
"""

import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pypdf import PdfReader
from pydantic import BaseModel, Field

from .segmentation import sentence_spans

#: Version of the extraction and segmentation rules. Any change that can
#: alter extracted units or identifiers requires bumping this version.
EXTRACTION_VERSION = "1.0"

# Failure reason codes (safe to export; no student content).
FAILURE_UNREADABLE = "unreadable-pdf"
FAILURE_NO_TEXT = "no-readable-text"
FAILURE_NO_OUTLINE = "no-usable-structure"
FAILURE_HEADING_UNMAPPED = "structure-mapping-failed"

FAILURE_MESSAGES = {
    FAILURE_UNREADABLE: "file is corrupt, inaccessible, or encrypted",
    FAILURE_NO_TEXT: "no readable text could be extracted",
    FAILURE_NO_OUTLINE: "document has no usable heading outline",
    FAILURE_HEADING_UNMAPPED: "outline headings could not be matched to page text",
}

# Standards-declaration warnings (extraction proceeds despite them).
WARNING_NO_PDFA = "missing-pdfa-declaration"
WARNING_NO_PDFUA = "missing-pdfua-declaration"

#: Vertical tolerance for merging text chunks into one line (points).
_LINE_MERGE_TOLERANCE_PT = 2.0
#: A same-page gap larger than median line gap times this factor starts a
#: new paragraph.
_PARAGRAPH_GAP_FACTOR = 1.35


class Sentence(BaseModel):
    """One sentence: an exact span of its paragraph's canonical text."""

    id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    pages: list[int] = Field(min_length=1)


class Paragraph(BaseModel):
    """One paragraph of a topic: canonical text with page provenance."""

    id: str
    text: str
    pages: list[int] = Field(min_length=1)
    sentences: list[Sentence]


class Topic(BaseModel):
    """One heading-aligned topic of a submission."""

    id: str
    title: str
    pages: list[int] = Field(min_length=1)
    paragraphs: list[Paragraph]


class SubmissionExtraction(BaseModel):
    """Structured content of one submission. Never exported with the manifest."""

    submission: str
    extraction_version: str
    topics: list[Topic]


class ExtractionOutcome(BaseModel):
    """Per-file result: status, warnings, and a safe failure reason.

    `extraction` holds the structured content in memory; batch exports must
    serialize only the metadata fields, never the extraction.
    """

    filename: str
    status: Literal["success", "failure"]
    warnings: list[str] = Field(default_factory=list)
    failure_code: str | None = None
    failure_reason: str | None = None
    extraction: SubmissionExtraction | None = None

    def metadata(self) -> "ExtractionOutcome":
        """Copy without extracted content, safe for exported metadata."""
        return self.model_copy(update={"extraction": None})


@dataclass
class _Line:
    """A reconstructed text line: page (0-based), baseline y, x, text."""

    page: int
    y: float
    x: float
    text: str


@dataclass
class _Heading:
    """An outline entry mapped to its heading line position."""

    title: str
    page: int
    y: float | None


def _matrix_multiply(m1, m2) -> tuple[float, ...]:
    """6-element PDF matrix product; m1 is applied in m2's coordinate space."""
    return (
        m1[0] * m2[0] + m1[1] * m2[2],
        m1[0] * m2[1] + m1[1] * m2[3],
        m1[2] * m2[0] + m1[3] * m2[2],
        m1[2] * m2[1] + m1[3] * m2[3],
        m1[4] * m2[0] + m1[5] * m2[2] + m2[4],
        m1[4] * m2[1] + m1[5] * m2[3] + m2[5],
    )


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _page_lines(page, page_index: int) -> list[_Line]:
    """Reconstruct reading-order lines from one page, excluding artifacts."""
    chunks: list[tuple[float, float, str]] = []
    marked_stack: list[str] = []

    def track_marked_content(operator, operands, _cm, _tm) -> None:
        if operator in (b"BDC", b"BMC"):
            marked_stack.append(str(operands[0]) if operands else "")
        elif operator == b"EMC" and marked_stack:
            marked_stack.pop()

    def collect_text(text, cm, tm, _font_dict, _font_size) -> None:
        if text.strip() and "/Artifact" not in marked_stack:
            matrix = _matrix_multiply(tm, cm)
            chunks.append((matrix[5], matrix[4], text))

    page.extract_text(
        visitor_text=collect_text, visitor_operand_before=track_marked_content
    )
    chunks.sort(key=lambda chunk: (-chunk[0], chunk[1]))

    lines: list[_Line] = []
    for y, x, text in chunks:
        if lines and abs(lines[-1].y - y) <= _LINE_MERGE_TOLERANCE_PT:
            lines[-1].text += text
        else:
            lines.append(_Line(page=page_index, y=y, x=x, text=text))
    return lines


def _document_lines(reader: PdfReader) -> list[_Line]:
    lines: list[_Line] = []
    for index, page in enumerate(reader.pages):
        lines.extend(_page_lines(page, index))
    return lines


def _outline_headings(reader: PdfReader) -> list[_Heading] | None:
    """Flatten the outline in document order; None when absent or unusable."""
    try:
        outline = reader.outline
    except Exception:
        return None
    if not outline:
        return None

    headings: list[_Heading] = []

    def walk(items) -> bool:
        for item in items:
            if isinstance(item, list):
                if not walk(item):
                    return False
                continue
            try:
                page = reader.get_destination_page_number(item)
            except Exception:
                return False
            dest = getattr(item, "dest_array", None)
            y = None
            if dest is not None and len(dest) > 3 and dest[3] is not None:
                y = float(dest[3])
            headings.append(_Heading(title=str(item.title), page=page, y=y))
        return True

    if not walk(outline):
        return None
    return headings


def _locate_heading(
    heading: _Heading,
    lines: list[_Line],
    page_lines: list[_Line],
    page_start: int,
) -> tuple[int, int] | None:
    """Find (start, end) line indexes of a heading within the document lines.

    Matches outline titles to reconstructed lines on the destination page,
    preferring the line nearest the destination y. Multi-line headings
    consume their continuation lines. Returns None when unmappable.
    """
    target = _normalize(heading.title)
    if not target:
        return None
    candidates = [
        page_start + i
        for i, line in enumerate(page_lines)
        if _normalize(line.text).startswith(target)
        or target.startswith(_normalize(line.text))
    ]
    if not candidates:
        return None
    if heading.y is not None:
        start = min(candidates, key=lambda i: abs(lines[i].y - (heading.y or 0)))
    else:
        start = candidates[0]

    end = start
    covered = _normalize(lines[start].text)
    while covered != target and target.startswith(covered):
        if end + 1 >= len(lines) or lines[end + 1].page != heading.page:
            break
        following = _normalize(lines[end + 1].text)
        if not target.startswith(covered + following):
            break
        end += 1
        covered += following
    return start, end


def _median_line_gap(lines: list[_Line]) -> float | None:
    gaps = [
        previous.y - current.y
        for previous, current in zip(lines, lines[1:])
        if previous.page == current.page and previous.y - current.y > 0
    ]
    return statistics.median(gaps) if gaps else None


@dataclass
class _MappedText:
    """Canonical text plus (0-based page, start, end) segments into it."""

    text: str
    segments: list[tuple[int, int, int]]

    def pages_between(self, start: int, end: int) -> list[int]:
        """1-based source pages overlapping the canonical span."""
        return sorted(
            {page + 1 for page, seg_start, seg_end in self.segments
             if seg_start < end and start < seg_end}
        )


def _join_lines(group: list[_Line]) -> _MappedText:
    """Canonical paragraph text from reading-order lines, with page mapping.

    Each line's whitespace is collapsed before joining, so segment offsets
    stay exact: a hyphen-final line joins the next line directly (the hyphen
    is dropped), otherwise lines join with a single space.
    """
    text = ""
    segments: list[tuple[int, int, int]] = []
    for line in group:
        line_text = re.sub(r"\s+", " ", line.text.strip())
        if not line_text:
            continue
        if text.endswith("-"):
            text = text[:-1]
            if segments:
                page, start, _end = segments[-1]
                segments[-1] = (page, start, len(text))
        elif text:
            segments.append((line.page, len(text), len(text) + 1))
            text += " "
        start = len(text)
        text += line_text
        segments.append((line.page, start, len(text)))
    return _MappedText(text=text, segments=segments)


def _split_paragraphs(
    content: list[_Line], median_gap: float | None
) -> list[list[_Line]]:
    """Group content lines into paragraphs by vertical gaps.

    A page boundary alone never splits a paragraph.
    """
    paragraphs: list[list[_Line]] = []
    for line in content:
        previous = paragraphs[-1][-1] if paragraphs else None
        is_break = (
            previous is not None
            and previous.page == line.page
            and median_gap is not None
            and previous.y - line.y > median_gap * _PARAGRAPH_GAP_FACTOR
        )
        if previous is None or is_break:
            paragraphs.append([line])
        else:
            paragraphs[-1].append(line)
    return paragraphs


def _declaration_warnings(reader: PdfReader) -> list[str]:
    """Warn about missing PDF/A and PDF/UA XMP declarations.

    Presence of a declaration is never treated as proof of conformance.
    """
    data = b""
    try:
        metadata = reader.trailer["/Root"].get("/Metadata")
        if metadata is not None:
            data = metadata.get_data().lower()
    except Exception:
        data = b""
    warnings = []
    if b"pdfaid" not in data:
        warnings.append(WARNING_NO_PDFA)
    if b"pdfuaid" not in data:
        warnings.append(WARNING_NO_PDFUA)
    return warnings


def _failure(
    filename: str, code: str, warnings: list[str] | None = None
) -> ExtractionOutcome:
    return ExtractionOutcome(
        filename=filename,
        status="failure",
        warnings=warnings or [],
        failure_code=code,
        failure_reason=FAILURE_MESSAGES[code],
    )


def extract_submission(path: Path) -> ExtractionOutcome:
    """Extract one submission PDF into topics and paragraphs.

    Always returns an outcome; expected per-file problems are failures with
    safe reason codes, not exceptions.
    """
    filename = path.name
    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            if reader.decrypt("") == 0:
                return _failure(filename, FAILURE_UNREADABLE)
        warnings = _declaration_warnings(reader)
        lines = _document_lines(reader)
        headings = _outline_headings(reader)
    except Exception:
        # Never propagate parser details: exception text can embed content.
        return _failure(filename, FAILURE_UNREADABLE)

    if not lines:
        return _failure(filename, FAILURE_NO_TEXT, warnings)
    if not headings:
        return _failure(filename, FAILURE_NO_OUTLINE, warnings)

    lines_by_page: dict[int, list[_Line]] = {}
    page_starts: dict[int, int] = {}
    for index, line in enumerate(lines):
        page_starts.setdefault(line.page, index)
        lines_by_page.setdefault(line.page, []).append(line)

    # Map every outline heading to its exact line span; refuse to fabricate
    # structure when the mapping fails.
    spans: list[tuple[int, int]] = []
    for heading in headings:
        located = _locate_heading(
            heading,
            lines,
            lines_by_page.get(heading.page, []),
            page_starts.get(heading.page, 0),
        )
        if located is None:
            return _failure(filename, FAILURE_HEADING_UNMAPPED, warnings)
        spans.append(located)
    positions = [start for start, _ in spans]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        return _failure(filename, FAILURE_HEADING_UNMAPPED, warnings)

    median_gap = _median_line_gap(lines)
    topics: list[Topic] = []
    paragraph_count = 0
    sentence_count = 0
    for index, (heading, (start, end)) in enumerate(zip(headings, spans)):
        content_end = spans[index + 1][0] if index + 1 < len(spans) else len(lines)
        content = lines[end + 1 : content_end]
        paragraphs: list[Paragraph] = []
        for group in _split_paragraphs(content, median_gap):
            paragraph_count += 1
            mapped = _join_lines(group)
            sentences: list[Sentence] = []
            for span_start, span_end in sentence_spans(mapped.text):
                sentence_count += 1
                sentences.append(
                    Sentence(
                        id=f"sent-{sentence_count}",
                        start=span_start,
                        end=span_end,
                        pages=mapped.pages_between(span_start, span_end),
                    )
                )
            paragraphs.append(
                Paragraph(
                    id=f"par-{paragraph_count}",
                    text=mapped.text,
                    pages=sorted({line.page + 1 for line in group}),
                    sentences=sentences,
                )
            )
        topic_pages = sorted(
            {heading.page + 1} | {page for par in paragraphs for page in par.pages}
        )
        topics.append(
            Topic(
                id=f"topic-{index + 1}",
                title=heading.title,
                pages=topic_pages,
                paragraphs=paragraphs,
            )
        )

    return ExtractionOutcome(
        filename=filename,
        status="success",
        warnings=warnings,
        extraction=SubmissionExtraction(
            submission=filename,
            extraction_version=EXTRACTION_VERSION,
            topics=topics,
        ),
    )
