# Proposal

## Why

The current CLI lists PDFs but does not extract their content. The next roadmap
phase needs reliable, traceable text units before criterion analysis can begin.

## What Changes

- Extract text and usable topic and paragraph structure from Typst-based PDFs
  with pypdf, including documents without PDF/A or PDF/UA declarations.
- Segment Finnish and English text into addressable sentences after comparing
  candidate approaches with representative, locally reviewed examples.
- Assign deterministic, versioned topic, paragraph, and sentence identifiers,
  scoped to a submission filename and preserving source-text traceability.
- Record per-file extraction failures and warnings while continuing the batch;
  a completed batch can succeed even if some submissions fail.
- Establish Git-ignored local storage for student PDFs and extracted material;
  use synthetic fixtures for automated tests.

Out of scope: OCR, full PDF/A or PDF/UA conformance certification, grading,
criterion analysis, and final evidence reports.

## Capabilities

### New Capabilities

- `pdf-extraction`: Extract structured, traceable text from submissions and
  report extraction outcomes safely.

### Modified Capabilities

None.

## Impact

- Extraction and batch orchestration in `src/siivila/`, existing CLI
  integration tests, and synthetic PDF fixtures.
- pypdf and potentially a sentence segmentation dependency; installation and
  compatibility must work on macOS and Roihu.
- Run manifest and local data handling, `.gitignore`, README, and Roihu setup
  instructions.
