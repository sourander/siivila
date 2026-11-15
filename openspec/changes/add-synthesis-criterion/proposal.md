# Proposal

## Why

The pipeline extracts submissions into traceable topics, paragraphs, and
sentences but evaluates nothing. Roadmap step 3 delivers the first real
criterion — synthesis of separate facts or sources — end to end, proving the
full loop (prompt → schema-constrained model call → deterministic evidence
validation → per-criterion JSON) that all later criteria reuse.

## What Changes

- Add a versioned synthesis criterion definition (v1.0): what qualifies as
  synthesis, what does not, and the expected output schema.
- Evaluate the criterion per submission with topic-level LLM calls through the
  existing `ModelBackend` protocol (fake in unit tests, MLX locally, vLLM on
  Roihu) — no new abstraction.
- Deterministically validate model findings: every `sentence_id` in a finding
  must resolve to a real sentence of that submission; unknown identifiers are
  rejected. Quotes are the exact extracted sentence spans, never model text.
- Aggregate topic-level findings into one per-criterion result JSON per
  submission (`status`, `instances`, `warnings`), written to `--output-dir`;
  the manifest records that the file exists, never its content.
- Per-submission criterion failure (e.g. invalid model output after bounded
  retries) is recorded like an extraction failure: the batch continues and
  still exits successfully.

Deliberately skipped (smallest version that works):

- No LangGraph dependency: one criterion is a linear loop, not a graph.
- No golden-set evaluation or prompt tuning: roadmap step 5.
- No Markdown/PDF report: roadmap step 8; JSON output is the deliverable.
- No cross-criterion framework, criterion registry, or config options: there
  is one criterion; generalize when the second one exists.

## Capabilities

### New Capabilities

- `synthesis-criterion`: versioned synthesis criterion evaluated per
  submission via topic-level model calls, with deterministic evidence
  validation against extracted sentence identifiers and a per-criterion JSON
  result whose quotes come from source text.

### Modified Capabilities

- `pdf-extraction`: batch outcome reporting gains criterion-result outcomes —
  the run result records each submission's criterion output filename or a
  safe failure reason, still without student text.

## Impact

- **Code**: `src/siivila/pipeline.py` (run criterion after extraction),
  new `src/siivila/criteria.py` (definition, prompt, output schema,
  evidence validation, aggregation).
- **Output**: `--output-dir` gains one `<submission>.synthesis.json` per
  evaluated submission; `manifest.json` records result filenames and outcomes.
- **Dependencies**: none added.
- **Environments**: unchanged — same code path via `uv run grade` locally and
  `srun python grade.py` on Roihu; unit tests use `FakeBackend`.
