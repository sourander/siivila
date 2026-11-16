"""Extraction tests with synthetic PDFs. No student content, no model."""

from pathlib import Path

import pytest

from siivila.extraction import (
    EXTRACTION_VERSION,
    FAILURE_HEADING_UNMAPPED,
    FAILURE_NO_OUTLINE,
    FAILURE_NO_TEXT,
    FAILURE_UNREADABLE,
    WARNING_NO_PDFA,
    WARNING_NO_PDFUA,
    extract_submission,
)
from tests.synthetic_pdf import (
    HEADING_SIZE,
    XMP_BOTH,
    XMP_NEITHER,
    XMP_PDFA_ONLY,
    XMP_PDFUA_ONLY,
    DrawnLine,
    OutlineEntry,
    build_pdf,
)

# Vertical layout: line gap 15pt within paragraphs, 24pt between paragraphs
# (mirrors the reference documents' ~15pt line and ~23.5pt paragraph gaps).
G = 15.0
P = 24.0


@pytest.fixture
def two_topic_pdf(tmp_path: Path) -> Path:
    """Two headings on one page, each with paragraphs of three lines."""
    page = [
        DrawnLine("First Topic", y=770, size=HEADING_SIZE),
        DrawnLine("Alpha one two.", y=770 - P),
        DrawnLine("Alpha three four.", y=770 - P - G),
        DrawnLine("Alpha five six.", y=770 - P - 2 * G),
        DrawnLine("Beta one two.", y=770 - 2 * P - 2 * G),
        DrawnLine("Beta three four.", y=770 - 2 * P - 3 * G),
        DrawnLine("Beta five six.", y=770 - 2 * P - 4 * G),
        DrawnLine("Second Topic", y=770 - 3 * P - 4 * G, size=HEADING_SIZE),
        DrawnLine("Gamma one two.", y=770 - 4 * P - 4 * G),
        DrawnLine("Gamma three four.", y=770 - 4 * P - 5 * G),
        DrawnLine("Gamma five six.", y=770 - 4 * P - 6 * G),
    ]
    return build_pdf(
        tmp_path / "two-topics.pdf",
        [page],
        outline=[
            OutlineEntry("First Topic", page=0, y=770),
            OutlineEntry("Second Topic", page=0, y=770 - 3 * P - 4 * G),
        ],
        xmp=XMP_BOTH,
    )


def test_two_headings_share_one_page(two_topic_pdf: Path):
    outcome = extract_submission(two_topic_pdf)
    assert outcome.status == "success"
    extraction = outcome.extraction
    assert extraction is not None
    assert [topic.title for topic in extraction.topics] == [
        "First Topic",
        "Second Topic",
    ]
    first, second = extraction.topics
    # Content is assigned by heading position, not by page number.
    assert [p.text for p in first.paragraphs] == [
        "Alpha one two. Alpha three four. Alpha five six.",
        "Beta one two. Beta three four. Beta five six.",
    ]
    assert [p.text for p in second.paragraphs] == [
        "Gamma one two. Gamma three four. Gamma five six."
    ]
    assert first.pages == [1] and second.pages == [1]
    assert [p.id for p in first.paragraphs] == ["par-1", "par-2"]
    assert [topic.id for topic in extraction.topics] == ["topic-1", "topic-2"]
    assert extraction.extraction_version == EXTRACTION_VERSION


def test_paragraph_continues_across_pages(tmp_path: Path):
    page1 = [
        DrawnLine("Only Topic", y=770, size=HEADING_SIZE),
        DrawnLine("Start of a long para-", y=770 - P),
        DrawnLine("graph that keeps going.", y=770 - P - G),
    ]
    page2 = [
        DrawnLine("7", y=30, artifact=True),  # page number: excluded
        DrawnLine("Still the same paragraph.", y=770),
        DrawnLine("And its final line.", y=770 - G),
    ]
    path = build_pdf(
        tmp_path / "spanning.pdf",
        [page1, page2],
        outline=[OutlineEntry("Only Topic", page=0, y=770)],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "success"
    paragraphs = outcome.extraction.topics[0].paragraphs
    assert len(paragraphs) == 1
    assert paragraphs[0].text == (
        "Start of a long paragraph that keeps going. "
        "Still the same paragraph. And its final line."
    )
    assert paragraphs[0].pages == [1, 2]
    assert "7" not in paragraphs[0].text


def test_content_before_first_heading_is_discarded(tmp_path: Path):
    page = [
        DrawnLine("Front Matter Title", y=770, size=HEADING_SIZE),
        DrawnLine("Contents listing line.", y=770 - P),
        DrawnLine("Real Topic", y=770 - 2 * P, size=HEADING_SIZE),
        DrawnLine("Body line one.", y=770 - 3 * P),
        DrawnLine("Body line two.", y=770 - 3 * P - G),
        DrawnLine("Body line three.", y=770 - 3 * P - 2 * G),
    ]
    path = build_pdf(
        tmp_path / "frontmatter.pdf",
        [page],
        outline=[OutlineEntry("Real Topic", page=0, y=770 - 2 * P)],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "success"
    assert len(outcome.extraction.topics) == 1
    texts = [p.text for p in outcome.extraction.topics[0].paragraphs]
    assert texts == ["Body line one. Body line two. Body line three."]


def test_finnish_characters_survive(tmp_path: Path):
    page = [
        DrawnLine("Päättely", y=770, size=HEADING_SIZE),
        DrawnLine("Ääni kaikuu öisin.", y=770 - P),
        DrawnLine("Yö on pimeä.", y=770 - P - G),
        DrawnLine("Päivä valkenee.", y=770 - P - 2 * G),
    ]
    path = build_pdf(
        tmp_path / "finnish.pdf",
        [page],
        outline=[OutlineEntry("Päättely", page=0, y=770)],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "success"
    assert outcome.extraction.topics[0].title == "Päättely"
    assert outcome.extraction.topics[0].paragraphs[0].text == (
        "Ääni kaikuu öisin. Yö on pimeä. Päivä valkenee."
    )


def test_no_outline_is_a_structure_failure(tmp_path: Path):
    path = build_pdf(
        tmp_path / "bare.pdf",
        [[DrawnLine("Just some text.", y=770)]],
        outline=None,
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "failure"
    assert outcome.failure_code == FAILURE_NO_OUTLINE
    assert outcome.extraction is None


def test_unmatched_heading_is_a_mapping_failure(tmp_path: Path):
    path = build_pdf(
        tmp_path / "mismatch.pdf",
        [[DrawnLine("Actual Heading", y=770, size=HEADING_SIZE)]],
        outline=[OutlineEntry("Missing Heading", page=0, y=770)],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "failure"
    assert outcome.failure_code == FAILURE_HEADING_UNMAPPED
    assert outcome.failure_reason


def test_textless_pdf_is_a_failure(tmp_path: Path):
    path = build_pdf(tmp_path / "blank.pdf", [[]], outline=None)
    outcome = extract_submission(path)
    assert outcome.status == "failure"
    assert outcome.failure_code == FAILURE_NO_TEXT


def test_garbage_file_is_unreadable(tmp_path: Path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a pdf at all" * 100)
    outcome = extract_submission(path)
    assert outcome.status == "failure"
    assert outcome.failure_code == FAILURE_UNREADABLE


@pytest.mark.parametrize(
    ("xmp", "expected"),
    [
        (XMP_BOTH, []),
        (XMP_PDFA_ONLY, [WARNING_NO_PDFUA]),
        (XMP_PDFUA_ONLY, [WARNING_NO_PDFA]),
        (XMP_NEITHER, [WARNING_NO_PDFA, WARNING_NO_PDFUA]),
        (None, [WARNING_NO_PDFA, WARNING_NO_PDFUA]),
    ],
)
def test_declaration_warnings(tmp_path: Path, xmp, expected):
    page = [
        DrawnLine("Topic", y=770, size=HEADING_SIZE),
        DrawnLine("Body one.", y=770 - P),
        DrawnLine("Body two.", y=770 - P - G),
        DrawnLine("Body three.", y=770 - P - 2 * G),
    ]
    path = build_pdf(
        tmp_path / "decl.pdf",
        [page],
        outline=[OutlineEntry("Topic", page=0, y=770)],
        xmp=xmp,
    )
    outcome = extract_submission(path)
    # Extraction proceeds despite missing declarations.
    assert outcome.status == "success"
    assert outcome.warnings == expected


def test_failure_keeps_warnings_without_content(tmp_path: Path):
    path = build_pdf(
        tmp_path / "bare.pdf",
        [[DrawnLine("Just some text.", y=770)]],
        outline=None,
        xmp=XMP_NEITHER,
    )
    outcome = extract_submission(path)
    assert outcome.status == "failure"
    assert outcome.warnings == [WARNING_NO_PDFA, WARNING_NO_PDFUA]
    assert outcome.extraction is None


def _prose_pdf(tmp_path: Path, name: str, lines: list[str]) -> Path:
    """One topic whose body lines form a single paragraph."""
    page = [DrawnLine("Topic", y=770, size=HEADING_SIZE)]
    page += [DrawnLine(text, y=770 - P - i * G) for i, text in enumerate(lines)]
    return build_pdf(
        tmp_path / name,
        [page],
        outline=[OutlineEntry("Topic", page=0, y=770)],
        xmp=XMP_BOTH,
    )


def test_sentence_spans_reconstruct_exactly(tmp_path: Path):
    path = _prose_pdf(tmp_path, "spans.pdf", [
        "First sentence here. Second",
        "sentence continues. A third",
        "one ends it.",
    ])
    outcome = extract_submission(path)
    paragraph = outcome.extraction.topics[0].paragraphs[0]
    assert paragraph.text == (
        "First sentence here. Second sentence continues. A third one ends it."
    )
    sentences = paragraph.sentences
    assert [s.id for s in sentences] == ["sent-1", "sent-2", "sent-3"]
    for sentence in sentences:
        assert paragraph.text[sentence.start:sentence.end] != ""
        assert not paragraph.text[sentence.start:sentence.end].startswith(" ")
        assert not paragraph.text[sentence.start:sentence.end].endswith(" ")
    assert [paragraph.text[s.start:s.end] for s in sentences] == [
        "First sentence here.",
        "Second sentence continues.",
        "A third one ends it.",
    ]
    assert [s.pages for s in sentences] == [[1], [1], [1]]


def test_sentence_spanning_pages_keeps_both_pages(tmp_path: Path):
    page1 = [
        DrawnLine("Topic", y=770, size=HEADING_SIZE),
        DrawnLine("A long sentence that starts here", y=770 - P),
    ]
    page2 = [DrawnLine("and finishes there. Short one.", y=770)]
    path = build_pdf(
        tmp_path / "spanning-sentence.pdf",
        [page1, page2],
        outline=[OutlineEntry("Topic", page=0, y=770)],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    paragraph = outcome.extraction.topics[0].paragraphs[0]
    first, second = paragraph.sentences
    assert paragraph.text[first.start:first.end] == (
        "A long sentence that starts here and finishes there."
    )
    assert first.pages == [1, 2]
    assert second.pages == [2]


def test_finnish_and_english_edge_cases(tmp_path: Path):
    path = _prose_pdf(tmp_path, "edge.pdf", [
        "Käytettiin esim. pudotusta. Malli",
        "oppi 3,5 tunnissa. Tulos oli",
        "\"aivan hyvä.\" Jatkuu myöhemmin.",
    ])
    outcome = extract_submission(path)
    paragraph = outcome.extraction.topics[0].paragraphs[0]
    assert [paragraph.text[s.start:s.end] for s in paragraph.sentences] == [
        "Käytettiin esim. pudotusta.",
        "Malli oppi 3,5 tunnissa.",
        "Tulos oli \"aivan hyvä.\"",
        "Jatkuu myöhemmin.",
    ]


def test_repeat_extraction_is_deterministic(two_topic_pdf: Path):
    first = extract_submission(two_topic_pdf)
    second = extract_submission(two_topic_pdf)
    assert first.model_dump() == second.model_dump()


def test_renamed_file_is_a_distinct_submission(two_topic_pdf: Path, tmp_path: Path):
    renamed = tmp_path / "resubmitted-v2.pdf"
    renamed.write_bytes(two_topic_pdf.read_bytes())
    first = extract_submission(two_topic_pdf).extraction
    second = extract_submission(renamed).extraction
    assert first.submission != second.submission
    assert first.submission == two_topic_pdf.name
    assert second.submission == "resubmitted-v2.pdf"
    # Same content and version, but a different submission identity.
    assert first.extraction_version == second.extraction_version
    assert first.model_dump(exclude={"submission"}) == second.model_dump(
        exclude={"submission"}
    )


def test_nested_subheadings_grouped_under_top_level_topic(tmp_path: Path):
    page = [
        DrawnLine("3 Koneoppiminen", y=770, size=HEADING_SIZE),
        DrawnLine("3.1 Mitä tehtiin ja teoriaa", y=770 - P, size=HEADING_SIZE),
        DrawnLine("Theory sentence one. Theory sentence two.", y=770 - 2 * P),
        DrawnLine("3.2 Tyypit - Tehtävät", y=770 - 3 * P, size=HEADING_SIZE),
        DrawnLine("Exercise sentence one.", y=770 - 4 * P),
    ]
    path = build_pdf(
        tmp_path / "nested.pdf",
        [page],
        outline=[
            OutlineEntry(
                "3 Koneoppiminen",
                page=0,
                y=770,
                children=[
                    OutlineEntry("3.1 Mitä tehtiin ja teoriaa", page=0, y=770 - P),
                    OutlineEntry("3.2 Tyypit - Tehtävät", page=0, y=770 - 3 * P),
                ],
            )
        ],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "success"
    extraction = outcome.extraction
    assert extraction is not None
    assert extraction.extraction_version == "1.1"
    assert [t.title for t in extraction.topics] == ["3 Koneoppiminen"]
    topic = extraction.topics[0]
    assert [p.subheading for p in topic.paragraphs] == [
        "3.1 Mitä tehtiin ja teoriaa",
        "3.2 Tyypit - Tehtävät",
    ]
    assert [p.text for p in topic.paragraphs] == [
        "Theory sentence one. Theory sentence two.",
        "Exercise sentence one.",
    ]
    assert [s.id for p in topic.paragraphs for s in p.sentences] == [
        "sent-1",
        "sent-2",
        "sent-3",
    ]


@pytest.mark.parametrize(
    ("refs_heading", "apps_heading", "sub_app_heading"),
    [
        ("Lähteet", "Liitteet", "Liite 1 Muistiinpanot"),
        ("References", "Appendices", "Appendix A Cheat Sheet"),
    ],
)
def test_references_extracted_and_appendices_excluded(
    tmp_path: Path, refs_heading: str, apps_heading: str, sub_app_heading: str
):
    page1 = [
        DrawnLine("1 Johdanto", y=770, size=HEADING_SIZE),
        DrawnLine("Intro claims something [1].", y=770 - P),
        DrawnLine("More detail follows [2].", y=770 - P - G),
        DrawnLine(refs_heading, y=770 - 2 * P - G, size=HEADING_SIZE),
        DrawnLine("1. Virtanen A. Ensimmäinen lähde-", y=770 - 3 * P - G),
        DrawnLine("teos. 2026.", y=770 - 3 * P - 2 * G),
    ]
    page2 = [
        # Starts right at top of page 2: must still split from reference 1.
        DrawnLine("2. Korhonen B. Toinen lähde. 2025.", y=770),
        DrawnLine(apps_heading, y=770 - P, size=HEADING_SIZE),
        DrawnLine(sub_app_heading, y=770 - 2 * P, size=HEADING_SIZE),
        DrawnLine("Appendix memo sentence that must not be graded.", y=770 - 3 * P),
    ]
    path = build_pdf(
        tmp_path / f"sections-{refs_heading}.pdf",
        [page1, page2],
        outline=[
            OutlineEntry("1 Johdanto", page=0, y=770),
            OutlineEntry(refs_heading, page=0, y=770 - 2 * P - G),
            OutlineEntry(
                apps_heading,
                page=1,
                y=770 - P,
                children=[OutlineEntry(sub_app_heading, page=1, y=770 - 2 * P)],
            ),
        ],
        xmp=XMP_BOTH,
    )
    outcome = extract_submission(path)
    assert outcome.status == "success"
    extraction = outcome.extraction
    assert extraction is not None
    assert [t.title for t in extraction.topics] == ["1 Johdanto"]
    assert len(extraction.references) == 2
    assert extraction.references[0].id == "ref-1"
    assert extraction.references[0].number == 1
    assert extraction.references[0].text == "Virtanen A. Ensimmäinen lähdeteos. 2026."
    assert extraction.references[0].pages == [1]
    assert extraction.references[1].id == "ref-2"
    assert extraction.references[1].number == 2
    assert extraction.references[1].text == "Korhonen B. Toinen lähde. 2025."
    assert extraction.references[1].pages == [2]
    all_sentences = [
        p.text[s.start : s.end]
        for t in extraction.topics
        for p in t.paragraphs
        for s in p.sentences
    ]
    assert all("Appendix memo" not in s for s in all_sentences)


