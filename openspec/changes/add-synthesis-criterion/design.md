# Design

## Context

See proposal.md — Why. Current state: `pipeline.run` extracts every
submission (topics → paragraphs → sentences with stable `sent-N` ids, exact
spans, page refs), runs one health-check call through `ModelBackend`, and
writes a metadata-only manifest. `backend.generate(prompts, schema)` already
delivers schema-validated Pydantic models with bounded retries and raises
`BackendError` on exhaustion. No criterion code exists yet.

## Goals / Non-Goals

**Goals:**

- One versioned synthesis criterion evaluated end to end per submission.
- Reuse what exists: `ModelBackend`, extraction spans, manifest, CLI.
- Unit tests run fully on `FakeBackend`; no model, no network.

**Non-Goals:**

- No LangGraph (one criterion is a linear loop; add orchestration when
  branching actually exists).
- No cross-topic synthesis calls, no golden set, no report rendering —
  later roadmap steps.
- No criterion registry/config: one criterion, defined in code.

## Decisions

### One new module: `src/siivila/criteria.py`

Holds the synthesis criterion v1.0: definition text, prompt builder, output
schema, evidence validation, aggregation. ~one screen of logic; a second
criterion later will show what (if anything) is worth generalizing.
Alternative considered: a `criteria/` package with a registry — rejected as
for-later structure.

### Output schema mirrors the README example

Per topic, the model returns findings: `{sentence_ids, classification,
rationale, uncertain}`. The aggregated result is
`{submission_id, criterion_id: "synthesis", criterion_version: "1.0",
status, instances, warnings}` where each instance additionally carries
`quotes` reconstructed from source spans. Status labels: `met` (at least one
accepted synthesis finding), `not_met` (none), `uncertain` (no accepted
finding but at least one finding flagged uncertain). Three labels cover the
criterion; more are speculation.

### One `generate` call per submission, not per topic

The backend takes a prompt list: pass all of the submission's topic prompts
in a single call — one call site, backend-side batching on vLLM for free.
Each prompt embeds the criterion definition, the topic title, and that
topic's sentences as `sent-N: text` lines — only that submission's text.

### Evidence validation is a dict lookup

Extraction already assigns `sent-N` ids with exact spans. Validation: build
`{id: sentence}` for the submission, reject any finding referencing an
unknown id (record a warning, keep going), and set `quotes` from
`paragraph.text[start:end]`. No fuzzy matching, no model involvement.

### Failure handling reuses the extraction pattern

`BackendError` (or any unexpected error) during a submission's evaluation is
caught per submission: outcome records a safe failure reason, the batch
continues, exit code stays 0. Failed extractions skip evaluation entirely
and inherit the extraction failure as their criterion outcome.

### Manifest: one additive field

`RunManifest` gains `criterion_results: list[{filename, criterion_id,
result_file | failure_reason}]` — filenames and safe reasons only. Result
files are named `<submission-stem>.synthesis.json` in `--output-dir`.
Additive change; no migration.

## Risks / Trade-offs

- [Topic-level calls miss cross-topic synthesis] → Accepted for v1.0; status
  is a deterministic aggregate of topic findings. Revisit with golden-set
  evidence in step 5.
- [Model invents sentence ids] → Rejected by the id lookup; counted as
  warnings so prompt quality is measurable later.
- [Small local model produces poor findings] → Smoke tests verify plumbing
  only; quality is measured on Roihu with the golden set, as documented.
