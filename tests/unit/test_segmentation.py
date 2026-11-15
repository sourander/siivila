"""Sentence segmentation regression tests. Synthetic fixtures, no model."""

import json
from pathlib import Path

from siivila.segmentation import sentence_spans

FIXTURE = Path(__file__).parent.parent / "fixtures" / "english_sentences.json"


def test_english_boundary_fixtures():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) >= 25  # the reviewed synthetic regression set
    for case in cases:
        text = case["text"]
        assert [text[start:end] for start, end in sentence_spans(text)] == case["sentences"], text


def test_spans_tile_text_without_separator_whitespace():
    text = "One two.  Three   four. Five."
    spans = sentence_spans(text)
    assert [text[s:e] for s, e in spans] == ["One two.", "Three   four.", "Five."]
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    # Interior whitespace between sentences is not part of any span.
    for (_, end), (next_start, _) in zip(spans, spans[1:]):
        assert text[end:next_start].strip() == ""
