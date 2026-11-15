# Tasks

## 1. Safe local data and dependencies

- [x] 1.1 Ignore `testdata/local/`, document its intended use and limitations,
  and verify with `git check-ignore` that files under it are excluded.
- [x] 1.2 Move both provided reference PDFs into the ignored directory without
  overwriting anything; verify both files are present and ignored.
- [x] 1.3 Add pypdf to the project dependencies and update the lockfile and
  local/Roihu installation instructions; verify installation and imports on
  the available target environment and document any unverified target.

## 2. PDF structure and provenance

- [x] 2.1 Inspect both local PDFs' outlines, tags, text mapping, and standards
  declarations without publishing student text; record only safe structural
  findings needed to implement extraction.
- [x] 2.2 Implement pypdf extraction of heading-aligned topics and ordered
  paragraphs with page provenance; verify synthetic PDFs covering same-page
  headings, page-spanning paragraphs, and missing or unreadable structure.
- [x] 2.3 Implement declaration warnings and explicit per-file failure reasons;
  verify synthetic cases for each missing declaration and unusable input.
- [x] 2.4 Add representative synthetic fixtures and replace placeholder
  invalid PDFs in the existing integration test as needed; verify the focused
  extraction and integration tests use no student content or model.

## 3. Sentences and stable identifiers

- [x] 3.1 Prepare the local Finnish and synthetic English boundary review sets
  described in the design; verify counts and keep student annotations ignored.
- [x] 3.2 Compare the rule-based baseline and spaCy sentencizer using
  per-language precision and recall, check Python/platform compatibility,
  record aggregate results, and select or improve an approach meeting the
  design gate; stop for a decision if the gate cannot be met.
- [x] 3.3 Add the selected segmentation dependency if needed and document
  local and Roihu installation; verify reproducible installation and offline
  operation on available environments.
- [x] 3.4 Implement deterministic canonical text, sentence offsets, page
  references, versioned IDs, and filename-scoped identity; verify repeat
  extraction, renamed files, Finnish and English edge cases, and exact
  canonical-span reconstruction with focused synthetic tests.

## 4. Batch integration and data handling

- [x] 4.1 Integrate per-file extraction into the existing CLI pipeline and
  extend the manifest while preserving its prior fields and health check;
  verify mixed and all-failed batches complete successfully and list outcomes.
- [x] 4.2 Ensure run-level errors remain nonzero and output contains no
  student text or unsafe exception details; verify focused failure and privacy
  tests, including no exported extracted content.
- [x] 4.3 Update the README roadmap and usage/data-handling guidance, plus any
  affected Slurm setup; verify a local batch and the existing Slurm dry-run
  export only safe results and clean job-local data.

## 5. End-to-end verification

- [x] 5.1 Run focused unit and integration tests and a local manual extraction
  of both reference PDFs; verify outcomes, versioned IDs, and warnings without
  committing or exporting student content.
