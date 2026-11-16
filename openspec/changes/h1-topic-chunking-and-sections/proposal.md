# Proposal

## Why

Flattening the PDF outline tree into one `Topic` per heading splits each weekly chapter (`H1`) across multiple separate `H2`/`H3` LLM calls (severing theory sub-sections from exercise sub-sections and producing empty 0-sentence calls for umbrella `H1` headings) while also sending non-graded back-matter sections (`Lähteet` / `References` and `Liitteet` / `Appendices`) to the model as ordinary essays. At the same time, `VllmBackend` currently omits `max_tokens` in `SamplingParams` and skips chat-template formatting, creating a parity gap with `MlxBackend` before production testing on Roihu.

## What Changes

- **H1-level topic chunking with subheading and paragraph context**: Group extracted `Topic` units by top-level (`H1`, outline depth 0) headings instead of flattening nested subheadings into separate topics. Nested outline subheadings (`H2`+, depth >= 1) are still matched and stripped from body lines so they do not become sentences, and their titles are recorded on the paragraphs that follow them (`Paragraph.subheading`). Bump `EXTRACTION_VERSION` from `"1.0"` to `"1.1"`.
- **Split out `Lähteet` / `References` and drop `Liitteet` / `Appendices`**:
  - Top-level bibliography headings (`"Lähteet"` or `"References"`) are separated from `SubmissionExtraction.topics` into structured `SubmissionExtraction.references` entries rather than evaluated as standalone content topics.
  - Top-level appendix headings (`"Liitteet"`, `"Appendices"`, or headings starting with `"Liite"` / `"Appendix"`) and their sub-sections are dropped from `SubmissionExtraction.topics` and excluded from evaluation altogether.
- **Richer H1 topic prompts**: Update `build_topic_prompt` and `build_submission_prompts` in `src/siivila/criteria.py` to skip empty (0-sentence) topics, render subheading and paragraph structure around `sent-N` lines, and append relevant extracted reference entries (`Lähteet` / `References`) so the model has bibliography context for in-text citations.
- **Fix `VllmBackend` parity bugs**: Configure `max_tokens=DEFAULT_MAX_TOKENS` in `VllmBackend` `SamplingParams`, apply the tokenizer chat template (with `enable_thinking=False` when supported) before inference, and use `_extract_json` during validation just like `MlxBackend`.

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `pdf-extraction`: Group `topics` by top-level (`H1`) outline headings while preserving subheading metadata on paragraphs, extract `"Lähteet"` / `"References"` into structured `references` outside `topics`, and drop `"Liitteet"` / `"Appendices"` (`"Liite"` / `"Appendix"`) from `topics` and evaluation.
- `synthesis-criterion`: Build one prompt per non-empty `H1` content topic (excluding references and appendices), include subheading/paragraph structure and cited reference entries in the prompt context.
- `llm-inference`: Ensure `VllmBackend` applies the model's chat template (with `enable_thinking=False` when supported) and bounds generation with `max_tokens=DEFAULT_MAX_TOKENS`.

## Impact

- **Code**: `src/siivila/extraction.py` (`EXTRACTION_VERSION = "1.1"`, outline depth tracking, `ReferenceEntry` model, `Paragraph.subheading`, `Lähteet`/`Liitteet` splitting), `src/siivila/criteria.py` (skip empty topics, include subheadings, paragraph grouping, and reference context in prompts), `src/siivila/backends.py` (`VllmBackend` chat template, `max_tokens`, and `_extract_json`).
- **Tests**: Update and expand `tests/unit/test_extraction.py`, `tests/unit/test_criteria.py`, `tests/unit/test_backends.py`, and `tests/synthetic_pdf.py` (support nested outline entries for `H1`/`H2` tests).
- **Dependencies**: None added.
