# Tasks

## 1. H1 Topic Chunking, Reference Extraction, and Appendix Exclusion

- [x] 1.1 Update `tests/synthetic_pdf.py` (`OutlineEntry` children / nesting support) and `src/siivila/extraction.py` to bump `EXTRACTION_VERSION = "1.1"`, track outline `depth`, group `Topic` units by top-level (`depth == 0`) headings, attach nested subheading titles (`depth >= 1`) to `Paragraph.subheading`, and exclude subheading lines from sentence spans; verify with unit tests in `tests/unit/test_extraction.py`.
- [x] 1.2 Add `ReferenceEntry` and `SubmissionExtraction.references` in `src/siivila/extraction.py`, extract top-level `"Lähteet"` / `"References"` sections into numbered reference entries (splitting on reference numbers across page boundaries as well as paragraph gaps), and exclude top-level `"Liitteet"` / `"Appendices"` (`"Liite"` / `"Appendix"`) sections and their subheadings from `topics` and `references`; verify with unit tests in `tests/unit/test_extraction.py`.

## 2. Enriched H1 Topic Prompts with Subheadings, Paragraphs, and Cited References

- [x] 2.1 Update `build_topic_prompt` and `build_submission_prompts` in `src/siivila/criteria.py` to skip empty (0-sentence) topics, render `Subheading:` headers and `[par-N]` paragraph groupings around `sent-N` lines, and append matching `SubmissionExtraction.references` entries for in-text numeric citations (`[1]`, `[1; 3]`, `[9–11]`); verify with unit tests in `tests/unit/test_criteria.py` and `uv run pytest`.

## 3. Inference Backend Parity

- [x] 3.1 Update `src/siivila/backends.py` so `VllmBackend` formats prompts and retry prompts with the shared tokenizer chat template helper (`enable_thinking=False` when supported), sets `max_tokens=DEFAULT_MAX_TOKENS` in `SamplingParams`, and extracts JSON via `_extract_json` before schema validation; verify with unit tests in `tests/unit/test_backends.py` and full `uv run pytest`.

## Workflow follow-up

- Run the local MLX smoke test (`uv run grade`) on the MacBook Pro against `testdata/local/referenssipaivakirja.pdf` and SCP the resulting output files back to this machine to inspect the H1-chunked synthesis output before archiving the change.
