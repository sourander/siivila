"""Deterministic sentence segmentation for Finnish and English.

Rule-based baseline: split after sentence-final punctuation followed by
whitespace and a plausible sentence start, except inside abbreviations,
decimals, ordinals, and similar constructs. Closing quotation marks and
brackets stay attached to the sentence they end.

Deterministic and offline: no models, no data files, no network access.
"""

import re

#: Words whose trailing period does not end a sentence (without the period,
#: lowercased). Finnish and common English scholarly abbreviations.
_ABBREVIATIONS = {
    # Finnish
    "esim", "jne", "n", "ts", "v", "vm", "ent", "huom", "ks", "tms", "tjsp",
    "ym", "eaa", "jaa", "toim", "prof", "tri", "s", "lk",
    # English
    "e.g", "i.e", "etc", "vs", "cf", "al", "fig", "dr", "mr", "mrs", "ms",
    "st", "approx", "dept", "est", "no", "vol", "pp", "ed", "eds",
}

#: Characters that may close a sentence after its final punctuation and
#: still belong to that sentence.
_CLOSERS = "\"'”’)]}"

#: Characters that may open a sentence before its first word.
_OPENERS = "\"'“‘(["

#: Punctuation + optional closers + whitespace: a candidate boundary.
_CANDIDATE = re.compile(r"[.!?…]+[\"'”’)\]]*(\s+)")

#: A bracketed numeric citation standing alone after a sentence's period
#: (an artifact of superscript extraction order, e.g. "... lause. [12]").
#: It belongs to the preceding sentence, never starts a new one.
_LONE_CITATION = re.compile(r"\[[\d;,\s–-]+\]\.?")


def _citation_end(text: str, start: int) -> int | None:
    """End offset of a lone citation at `start`, or None."""
    match = _LONE_CITATION.match(text, start)
    return match.end() if match else None


def _token_before(text: str, period_index: int) -> str:
    """The word (with inner dots) immediately before a period."""
    start = period_index
    while start > 0 and (text[start - 1].isalpha() or text[start - 1] == "."):
        start -= 1
    return text[start:period_index]


def _is_abbreviation(text: str, period_index: int) -> bool:
    token = _token_before(text, period_index)
    if not token:
        return False
    if token.lower().rstrip(".") in _ABBREVIATIONS:
        return True
    # Single-letter initial ("A. Virtanen") or dotted acronym ("U.S.").
    parts = token.rstrip(".").split(".")
    return all(len(part) <= 1 for part in parts)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return start-inclusive/end-exclusive sentence spans of `text`.

    Spans exclude the whitespace separating sentences, so
    `text[start:end]` is the exact sentence text.
    """
    cuts: list[tuple[int, int]] = []  # (sentence end, next sentence start)
    for match in _CANDIDATE.finditer(text):
        punct = match.start()
        end = match.end() - len(match.group(1))
        next_start = match.end()
        if next_start >= len(text):
            continue
        following = text[next_start]
        if not (following.isupper() or following.isdigit() or following in _OPENERS):
            continue
        if text[punct] == ".":
            # Decimal ("3.14") or ellipsis inside a sentence ("ja niin... edespäin").
            if punct > 0 and punct + 1 < len(text) and (
                text[punct - 1].isdigit() and text[punct + 1].isdigit()
            ):
                continue
            if _is_abbreviation(text, punct):
                continue
        citation_end = _citation_end(text, next_start)
        if citation_end is not None:
            # A lone citation attaches to the sentence just ended; the real
            # boundary, if any, comes after it.
            if citation_end >= len(text):
                continue
            if text[citation_end].isspace():
                after = citation_end
                while after < len(text) and text[after].isspace():
                    after += 1
                if after >= len(text):
                    continue
                if not (
                    text[after].isupper()
                    or text[after].isdigit()
                    or text[after] in _OPENERS
                ):
                    continue
                cuts.append((citation_end, after))
            continue
        cuts.append((end, next_start))

    spans: list[tuple[int, int]] = []
    start = 0
    for end, next_start in cuts:
        if text[start:end].strip():
            while start < end and text[start].isspace():
                start += 1
            spans.append((start, end))
        start = next_start
    end = len(text)
    while end > start and text[end - 1].isspace():
        end -= 1
    while start < end and text[start].isspace():
        start += 1
    if start < end:
        spans.append((start, end))
    return spans
