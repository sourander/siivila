# Sentence segmentation benchmark (task 3.2)

Date: 2026-11-14. Aggregate counts only; the reviewed Finnish text and
annotations stay in the Git-ignored `testdata/local/review/` directory.

## Review sets

- Finnish: 21 paragraphs from the local reference document, 110 sentence
  boundaries reviewed locally. Review found and corrected 4 false-positive
  splits (lone trailing citations like `[12]` extracted after a sentence's
  period); the correction is implemented in the baseline.
- English: 28 synthetic cases, 33 boundaries (abbreviations, decimals,
  citations, quoted endings), committed at `tests/fixtures/english_sentences.json`.

## Aggregate results

| Approach            | FI precision | FI recall | EN precision | EN recall |
|---------------------|--------------|-----------|--------------|-----------|
| rule-based baseline | 1.0000       | 1.0000    | 1.0000       | 1.0000    |
| spaCy sentencizer   | 0.9649       | 1.0000    | 0.8250       | 1.0000    |

Gate: ≥95% precision and recall per language.

## Compatibility

- spaCy 3.8.18 installs and its rule-based sentencizer runs offline on
  Python 3.14.2 / macOS (Apple Silicon). Roihu (aarch64 Linux) installation
  was not verifiable from the development machine.
- Rule-based baseline: pure Python, no dependencies, trivially offline.

## Decision

Selected the **rule-based baseline** (`src/siivila/segmentation.py`): it
meets the gate in both languages and is the simplest compatible candidate
(no new dependency). spaCy's sentencizer fails the English precision gate
(0.825 < 0.95), over-splitting abbreviations, decimals, and citations.
