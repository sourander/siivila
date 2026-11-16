# Proposal

## Why

Creating a teacher-verified golden set from initial model predictions (`<stem>.<criterion>.json`) requires inspecting each finding in the context of the full submission, removing false positives, adding missed evidence spans, adjusting sentence boundaries, editing rationales, and toggling uncertainty. Doing this by hand in raw JSON against a separate PDF viewer is slow and error-prone because quotes must exactly match extracted sentence spans (`sent-N`) and overall criterion status must stay consistent.

## What Changes

- Add a `review` CLI script entry point (`siivila.review:main`) that launches a local NiceGUI application pointed at a directory of criterion result files (`--dir`, with optional `--pdf-dir` override).
- Render the extracted submission structure (topics, subheadings, paragraphs, clickable `sent-N` sentences, and bibliography references) with color-coded highlights for confirmed, uncertain, and currently selected evidence instances.
- Allow selecting any submission and criterion present in the target directory (or defined in `criteria/*.yaml`), and adding, updating, or deleting evidence instances with deterministic quote reconstruction (`sentence_lookup`) and status aggregation (`aggregate_status`) saved directly back to `<stem>.<criterion>.json`.
- Add `nicegui` to the `dev` dependency group so local review works via `uv run review` without adding web UI dependencies to the production Slurm environment.

## Capabilities

### New Capabilities
- `review-mode`: Interactive local review and editing of per-submission criterion evidence against the extracted submission text.

### Modified Capabilities

## Impact

- `pyproject.toml`: Add `review = "siivila.review:main"` under `[project.scripts]` and `nicegui` under `[dependency-groups] dev`.
- `src/siivila/review.py`: New module implementing file discovery, deterministic instance CRUD helpers, and the NiceGUI interface.
- `tests/unit/test_review.py`: Unit tests for discovery and evidence add/update/delete/save helpers without requiring a browser or model.
- Existing extraction, criterion, pipeline, and Slurm batch code remain unchanged.
