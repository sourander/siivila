# Tasks

## 1. Dependencies and Entry Point

- [x] 1.1 Add `nicegui` to `[dependency-groups] dev` and `review = "siivila.review:main"` to `[project.scripts]` in `pyproject.toml`, and verify with `uv sync` that `uv run review --help` is callable.

## 2. Review Data Helpers and CLI Validation

- [x] 2.1 Implement directory resolution, submission/criterion discovery, and deterministic instance add/update/delete/save functions in `src/siivila/review.py`, and verify with unit tests in `tests/unit/test_review.py` (`uv run pytest tests/unit/test_review.py`).
- [x] 2.2 Implement the `review` CLI argument parser (`--dir`, optional `--pdf-dir`, `--port`) and error handling for invalid directories in `src/siivila/review.py`, and verify CLI validation tests pass in `tests/unit/test_review.py`.

## 3. NiceGUI Review Interface and Documentation

- [x] 3.1 Implement the NiceGUI page in `src/siivila/review.py` rendering submission/criterion selectors, topics/subheadings/paragraphs with clickable highlighted `sent-N` spans, references, and the evidence editor (add, edit, delete, uncertain toggle, rationale input), and verify it loads `testdata/local/out` cleanly.
- [x] 3.2 Document the `uv run review --dir <results-dir>` command in `README.md` and verify the full unit test suite passes with `uv run pytest tests/unit`.
