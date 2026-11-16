# Design

## Context

`extract_submission(pdf_path)` in `src/siivila/extraction.py` deterministically parses a submission PDF into a `SubmissionExtraction` hierarchy (`topics` -> `paragraphs` -> `sentences` with `sent-N` IDs and character offsets, plus `references`) in ~0.4 seconds. `src/siivila/criteria.py` defines `CriterionResult`, `SynthesisInstance`, `sentence_lookup(extraction)`, `aggregate_status(instances)`, and `load_criteria()`. `manifest.json` in a grading output directory already records `input_dir`. See `proposal.md` for motivation and `specs/review-mode/spec.md` for behavioral requirements.

## Goals / Non-Goals

**Goals:**
- Provide the smallest single-module review tool (`src/siivila/review.py`) that reuses existing extraction and criterion validation primitives without modifying `extraction.py`, `pipeline.py`, `criteria.py`, or `cli.py`.
- Keep all data mutation and file discovery logic in pure functions that can be unit-tested without launching a web server or browser.
- Isolate the UI dependency (`nicegui`) in the `dev` dependency group so the production Slurm environment on CSC Roihu is unaffected.

**Non-Goals:**
- Persisting a separate `<stem>.extraction.json` file during `grade` batch runs (which would require filtering in `slurm/grade.slurm` to avoid exporting student text).
- Free-text quote editing or sub-sentence character selection (evidence always operates at `sent-N` granularity).
- Multi-user server deployment or authentication (this is a local single-user developer/teacher tool).

## Decisions

### On-demand PDF extraction instead of pre-exported extraction JSON
Call `extract_submission(pdf_path)` in memory when loading a submission in `review`, resolving the PDF directory from `--pdf-dir`, `manifest.json` (`input_dir`), `--dir`, or `--dir`'s parent directory.
- *Alternative considered:* Have `grade` write `<stem>.extraction.json` into `--output-dir`. Rejected because `extract_submission` takes ~0.4s per PDF, and writing full student text to `--output-dir` would conflict with the `pdf-extraction` requirement and `slurm/grade.slurm` copy rule that exported batch results must never contain full extracted student text.

### Separate `review` script entry point and `dev` dependency
Register `review = "siivila.review:main"` under `[project.scripts]` in `pyproject.toml` and add `nicegui` to `[dependency-groups] dev`.
- *Alternative considered:* Subcommand on `grade` and core dependency. Rejected because `grade` runs in headless Slurm jobs on Roihu where web UI dependencies are unnecessary.

### Sentence-level clickable spans in NiceGUI
Render each `Sentence` (`sent-N`) inside its paragraph as an inline interactive element (or HTML with click handler) styled by state:
- Selected in editor: blue highlight/ring
- Confirmed instance (`uncertain=False`): green highlight with instance index badge(s)
- Uncertain instance (`uncertain=True`): amber highlight with instance index badge(s)
- Unreferenced sentence: normal text with hover highlight

Clicking a sentence toggles its `sent-N` ID in the active editor selection (sorted in numerical sentence order). Saving an instance calls `sentence_lookup(extraction)` to populate `quotes`, `aggregate_status(result.instances)` to recompute `status`, and writes `result.model_dump_json(indent=2) + "\n"` to `<stem>.<criterion>.json`.

## Risks / Trade-offs

- [Original PDF must be locally accessible when reviewing] -> Resolve `input_dir` automatically from `manifest.json` and provide `--pdf-dir` when reviewing moved result directories.
- [A sentence can belong to multiple evidence instances] -> Display all matching instance numbers on the sentence badge and highlight the active instance's sentences distinctly when an instance is selected for editing.
