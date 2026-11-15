# Design

## Context

The CLI currently discovers filenames and performs a model health check; it does
not parse PDFs. The manifest contains filenames and metadata only. The Slurm
script exports results after a successful CLI exit and removes job-local data.
See the proposal for motivation and the spec for behavioral requirements.

## Goals / Non-Goals

**Goals:**

- Provide a deterministic extraction representation usable by later phases.
- Preserve the existing CLI and health check while reporting per-file outcomes.
- Exercise the two local reference PDFs without making them test dependencies
  or committing their contents.

**Non-Goals:**

- Certifying PDF/A or PDF/UA, recovering scanned documents with OCR, or
  supporting arbitrary layouts without evidence that they can be parsed.
- Persisting extracted student text in exported reports or implementing
  criterion evaluation.

## Decisions

### Extraction and structure

Use pypdf to read metadata, outlines, page content, and available structure
information. Inspect the two reference files locally during implementation to
determine how Typst's heading and paragraph tags relate to page text. A tag or
outline alone is not proof that its text can be mapped accurately. Explicitly
map heading boundaries at sub-page granularity and retain page provenance;
handle paragraphs spanning pages. If the required mapping cannot be established
reliably, return a per-file failure instead of silently fabricating a topic.

An outline-only page split is simpler but fails when headings share a page.
Font-size inference and OCR are out of scope. Missing conformance declarations
produce warnings when structure is usable; detecting declarations is not
validation of actual compliance. Tests must cover each declaration independently.

### Sentence segmentation

Compare a conservative rule-based baseline with spaCy's rule-based
sentencizer on identical, locally reviewed Finnish and English examples. Check
Python 3.14 and macOS/Roihu installation compatibility before choosing a
dependency; do not download data or send student text to an external service
at runtime.

For a reproducible initial gate, review at least 100 Finnish sentence
boundaries from the local reference document and at least 30 boundaries in
synthetic English prose, including abbreviations, decimals, citations, and
quoted endings. Record boundary precision and recall for each candidate,
per language; use at least 95% for each metric in each language as an initial
acceptance target. Choose the simplest compatible candidate meeting the gate;
if neither does, improve the approach or bring the results back for a decision
instead of claiming the task is complete. These sample-size and quality targets
are proposed defaults, not evidence that either approach already meets them.
Keep reviewed student text and annotations in the ignored local directory;
only aggregate counts and synthetic regression cases may be committed.

### Representation and identifiers

Represent a submission as ordered topics containing paragraphs and sentence
spans. Store canonical extracted paragraph text once; sentence spans use
start-inclusive/end-exclusive character offsets into that text, with the
source page or pages retained. Canonicalization rules must be explicit and
deterministic. A span is exact relative to canonical extracted text, not a
guarantee that PDF extraction perfectly reproduces the visual original.

Scope IDs by filename, extraction version, and ordered positions; keep
paragraph and sentence identifiers unique within the submission. Repeating the
same file with the same version and configuration produces the same units and
IDs. Changes to extraction or segmentation rules that can alter IDs require
an extraction-version change. A renamed file is a different submission; a
revision must use a distinct filename.

### Batch results and data handling

Run extraction per file, isolate expected file-level parsing failures, and add
filename, status, warnings, and safe reason codes/messages to the manifest.
Continue after such failures and return success when the batch completes,
including an all-failed batch; run-level errors remain nonzero. Keep the
existing manifest information and health-check behavior. Never include
extracted text or exception messages containing student content in exported
metadata or logs.

Keep extracted representations in memory where possible, or under the
job-local directory on Roihu; never export them with the metadata-only
manifest. For local work, use a dedicated ignored `testdata/local/` directory
for PDFs, annotations, and extracted outputs. Move the two provided files
there only during implementation, after the ignore rule is in place and
without overwriting existing files. Synthetic fixtures remain separate and
committable. `.gitignore` is a safeguard, not a guarantee against force-adds
or files outside the ignored location; document that limitation.

## Risks / Trade-offs

- [Tagged PDF text mapping is more involved than reading outlines] -> Validate
  real reference files locally and use synthetic cases for same-page headings,
  page-spanning paragraphs, and missing mappings.
- [Segmentation may be inaccurate despite a small review sample] -> Publish
  aggregate benchmark counts and preserve edge cases as synthetic regressions;
  revisit quality with the later teacher-verified golden set.
- [PDF extraction may reorder or normalize text] -> Preserve page references
  and explicit canonical text offsets; do not claim visual fidelity or full
  standards certification.
- [Failure details or benchmark artifacts could contain student content] ->
  Use safe reason codes and keep local annotations out of Git and exported
  results.
- [A new dependency may not be available in the Roihu environment] -> Check
  both target platforms and update documented installation commands.

## Migration Plan

Introduce the ignore rule before relocating the supplied PDFs, add dependencies
and synthetic fixtures, then integrate extraction without removing existing
manifest fields. Update local and Roihu setup documentation. Reverting the
feature restores the filename-only manifest; leave local student files in the
ignored directory and do not delete them.
