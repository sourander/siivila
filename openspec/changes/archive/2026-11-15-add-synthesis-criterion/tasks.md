# Tasks

## 1. Synthesis criterion module

- [x] 1.1 Create `src/siivila/criteria.py` with the synthesis criterion v1.0 definition (what qualifies / does not qualify), the topic output schema (`sentence_ids`, `classification`, `rationale`, `uncertain`), and the aggregated result schema (`submission_id`, `criterion_id`, `criterion_version`, `status` ∈ met/not_met/uncertain, `instances`, `warnings`); verify the module imports and both schemas validate a hand-written example.
- [x] 1.2 Implement the prompt builder: criterion definition + topic title + the topic's sentences as `sent-N: text` lines, one prompt per topic, only that submission's text; verify a unit test asserts the prompt contains the sentence ids and no other submission's content.
- [x] 1.3 Implement evidence validation: build the `{sent-N: sentence}` lookup from the extraction, reject findings with unknown ids (record a warning), and attach `quotes` from the exact paragraph spans; verify unit tests cover unknown-id rejection and exact quote reconstruction.
- [x] 1.4 Implement status aggregation (any accepted finding → met; none → not_met; only uncertain findings → uncertain); verify a unit test covers all three labels.

## 2. Pipeline integration

- [x] 2.1 Extend `pipeline.run` to evaluate each successfully extracted submission with one `backend.generate` call of all its topic prompts, write `<stem>.synthesis.json` to `--output-dir`, and skip failed extractions; verify an integration test with `FakeBackend` produces a valid result file whose quotes match the synthetic fixture text.
- [x] 2.2 Catch per-submission evaluation errors and record a safe failure reason (no student text), continuing the batch with exit code 0; verify an integration test with a failing `FakeBackend` covers this.
- [x] 2.3 Add `criterion_results` (filename, criterion id, result filename or failure reason) to `RunManifest`; verify a test asserts the manifest contains no findings, quotes, or student text.
- [x] 2.4 Update README (criterion design section: synthesis v1.0 is implemented; roadmap step 3 marked done with the archive path; smoke tests run `uv run grade` with an unversioned `--input-dir` of PDFs and `--output-dir` for JSON outputs, with all code in git) and verify the documented commands still match the CLI.

## 3. Verification

- [x] 3.1 Run `uv run pytest` and verify the full suite passes.
- [x] 3.2 Run a smoke test with `uv run grade` pointing `--input-dir` at a gitignored PDF directory and `--output-dir` at an output directory, and verify `manifest.json` and `<stem>.synthesis.json` (with resolvable quotes) are written to `--output-dir`.

## Workflow follow-up

- Archive the change after review (`openspec archive add-synthesis-criterion`).
