# Design

## Context

See `proposal.md` — Why. Currently, `_outline_headings()` in `src/siivila/extraction.py` flattens the nested list structure returned by `pypdf.PdfReader.outline` into a 1D list of `_Heading` items, turning every `H1`, `H2`, and `H3` bookmark into a peer `Topic`. In `src/siivila/criteria.py`, `build_topic_prompt()` flattens all paragraphs of a topic into a continuous list of `sent-N: <text>` lines and generates a prompt even when a topic has 0 sentences or is a `Lähteet` / `Liitteet` back-matter section. Meanwhile, `VllmBackend` in `src/siivila/backends.py` calls `self._llm.generate(prompts, params)` with raw strings and omits `max_tokens` in `SamplingParams`.

## Goals / Non-Goals

**Goals:**

- Keep one `Topic` per top-level (`H1`, depth 0) content section while preserving nested subheading titles on `Paragraph.subheading` and excluding subheading lines from sentence spans.
- Deterministically separate `Lähteet` / `References` into `SubmissionExtraction.references` and drop `Liitteet` / `Appendices` (`Liite` / `Appendix`) from extracted `topics` and evaluation.
- Give the LLM coherent weekly chapter context (`H1` title, `H2` subheadings, paragraph boundaries, and bibliography entries cited in that topic) in a single call per `H1` topic.
- Align `VllmBackend` with `MlxBackend` on chat-template application, `max_tokens=DEFAULT_MAX_TOKENS`, and `_extract_json` cleanup.

**Non-Goals:**

- Implementing new criteria (such as `conversation with sources` or `course_book`) in this change — those remain upcoming roadmap steps that will consume `SubmissionExtraction.references`.
- Modifying how `validate_findings` or `aggregate_status` works — `sent-N` dictionary validation and quote reconstruction remain unchanged.

## Decisions

### 1. Outline depth tracking and `H1` topic grouping in `extraction.py`

`_Heading` gains `depth: int` (`0` for top-level items in `reader.outline`, incremented by `1` for each nested list level). Every outline heading (at any depth) is still located via `_locate_heading()` and checked for strictly increasing line positions so malformed outlines continue to fail fast with `FAILURE_HEADING_UNMAPPED`.

Top-level headings (`depth == 0`) partition the document into top-level sections: each top-level section spans from its heading's `(start, end)` to the next `depth == 0` heading's `start` (or `len(lines)`). Within a top-level content section, nested headings (`depth >= 1`) divide the body lines into sub-ranges:
- Lines before the first nested heading have `subheading = None`.
- Each nested heading (`sub_start, sub_end`) sets `subheading = nested_heading.title` for the body lines between `sub_end + 1` and the next heading's `start`, excluding the nested heading's own lines (`sub_start..sub_end`) from paragraph and sentence extraction.
- `Paragraph` gains `subheading: str | None = None`.
- `EXTRACTION_VERSION` bumps from `"1.0"` to `"1.1"`.

Alternative considered: introducing a nested `Subtopic` model between `Topic` and `Paragraph` (`Topic.subtopics -> Subtopic.paragraphs`). Rejected because keeping `Topic.paragraphs` flat with an optional `Paragraph.subheading` preserves the existing `Topic -> Paragraph -> Sentence` traversal used across `criteria.py` and existing tests.

### 2. Template-aligned classification of `Lähteet` / `References` and `Liitteet` / `Appendices`

Typst submissions use fixed Finnish or English back-matter heading titles:
- **References headings**: `{"lähteet", "references"}` (matched case-insensitively on `heading.title.strip().casefold()`).
- **Appendices headings**: `{"liitteet", "appendices"}` or a top-level title matching `r"^(liite|appendix)\b"` (case-insensitive).

When iterating over top-level (`depth == 0`) sections:
- **Appendices**: The entire top-level section (including any nested `Liite N` / `Appendix N` headings inside it) is skipped. No `Topic`, `Paragraph`, or `Sentence` is emitted.
- **References**: Instead of building a `Topic` with `sent-N` sentences, the section's lines are parsed into `SubmissionExtraction.references: list[ReferenceEntry]`, where:
  ```python
  class ReferenceEntry(BaseModel):
      id: str
      number: int | None = None
      text: str
      pages: list[int] = Field(min_length=1)
  ```
  Reference lines are grouped into individual entries by splitting whenever a line begins with a reference number pattern (`r"^\s*(?:\[(\d+)\]|(\d+)\.)\s+"`) or has a vertical paragraph gap. This ensures that a numbered reference starting at the top of a new page (`12. ...` on page 48 after `11. ...` at the bottom of page 47) is never merged into the previous reference entry.

### 3. Structured H1 prompt formatting with cited references in `criteria.py`

`build_submission_prompts()` filters `extraction.topics` to topics that contain at least one sentence (`any(p.sentences for p in topic.paragraphs)`), eliminating empty `(no sentences)` LLM calls when an `H1` section has no body text.

`build_topic_prompt(topic, criterion, course_config, references=None)`:
- Renders `Subheading: <title>` whenever `paragraph.subheading` changes within the topic, and separates paragraphs with `[par-N]` headers so the model sees both sub-section and paragraph discourse boundaries while still referencing `sent-N` IDs.
- Extracts integer citation numbers referenced in the topic's text (supporting single numbers `[1]`, semicolon/comma lists `[1; 3]`, and ranges `[9–11]` or `[9-11]`) and, when matching entries exist in `references`, appends a `References cited in this topic:` block at the bottom of the prompt.

### 4. Backend parity in `backends.py`

Extract a shared `_format_chat_prompt(tokenizer, prompt: str) -> str` helper used by both `MlxBackend` and `VllmBackend`:
- When `tokenizer` has a non-empty `chat_template`, format `[{"role": "user", "content": prompt}]` via `apply_chat_template(..., tokenize=False, add_generation_prompt=True, enable_thinking=False)` (falling back to calling without `enable_thinking` on `TypeError`).
- In `VllmBackend.generate()`, obtain the tokenizer via `getattr(self._llm, "get_tokenizer", lambda: None)()`, format each prompt (and retry prompt) through `_format_chat_prompt`, set `max_tokens=DEFAULT_MAX_TOKENS` in `SamplingParams`, and pass output text through `_extract_json(text)` before `schema.model_validate_json()`.

## Risks / Trade-offs

- [Long H1 topics increase per-prompt token count from ~500 to ~1,500–2,500 tokens] → Still well under 5% of the 64K context limit and reduces total prompt overhead (fewer repeated system/criterion headers per submission).
- [Unnumbered bibliography entries in `Lähteet` / `References`] → Fall back to paragraph-gap splitting with `number=None` so unnumbered references are still preserved in `SubmissionExtraction.references` without failing extraction.
- [Roihu vLLM environment cannot be tested on the 16 GB dev machine] → Unit tests in `tests/unit/test_backends.py` verify `SamplingParams(max_tokens=DEFAULT_MAX_TOKENS, ...)`, chat-template application, and `_extract_json` against a fake `vllm` module; MacBook Pro MLX smoke testing validates the end-to-end extraction and prompt changes locally.
