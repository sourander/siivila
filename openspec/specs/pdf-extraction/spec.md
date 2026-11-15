# PDF Extraction Specification

## Purpose

Provide structured, traceable text units and explicit extraction outcomes for
student PDF submissions before criterion analysis.

## Requirements

### Requirement: Structured submission extraction
The system SHALL extract readable text from supported Finnish and English
Typst-template PDFs into an ordered hierarchy of topics, paragraphs, and
sentences. Topic boundaries SHALL follow document headings rather than
arbitrary text chunks.

#### Scenario: Headings and paragraphs are available
- **WHEN** a readable submission contains usable heading and paragraph structure
- **THEN** its extracted content preserves topic order, paragraph order, and sentence order

#### Scenario: Multiple headings share a page
- **WHEN** two topic headings occur on the same page
- **THEN** content is assigned to the appropriate topic rather than solely by page number

#### Scenario: Paragraph continues across pages
- **WHEN** a paragraph continues across a page boundary
- **THEN** the extracted representation retains its complete text in reading order

### Requirement: Sentence boundaries
The system SHALL support deterministic sentence segmentation for Finnish and
English and SHALL preserve the extracted text associated with each sentence.

#### Scenario: Common punctuation and citations
- **WHEN** a paragraph contains ordinary abbreviations, decimals, or citations in Finnish or English
- **THEN** sentence boundaries do not split inside those constructs in the supported test cases

#### Scenario: Boundary after quotation
- **WHEN** a sentence ends with punctuation followed by a closing quotation mark
- **THEN** the quotation mark remains associated with that sentence

### Requirement: Stable source identifiers
The system SHALL assign unique topic, paragraph, and sentence identifiers
within each submission and expose the extraction version used to generate
them. Submission identity SHALL be the input filename.

#### Scenario: Repeat extraction
- **WHEN** the same file is extracted twice with the same extraction version and configuration
- **THEN** the same ordered units have the same identifiers

#### Scenario: Resubmitted file
- **WHEN** a revised submission has a different filename
- **THEN** it is treated as a distinct submission

### Requirement: Traceable extracted text
The system SHALL retain source page references and deterministic text spans
that locate each sentence in its extracted paragraph representation.

#### Scenario: Locate sentence text
- **WHEN** a downstream component resolves a sentence identifier
- **THEN** it can retrieve the exact corresponding span of extracted paragraph text and its source page references

### Requirement: Usability and standards declarations
The system SHALL process a structurally usable submission even if its PDF/A
or PDF/UA declaration is missing, and SHALL report a warning for the missing
declaration. It SHALL NOT claim standards conformance based on declarations alone.

#### Scenario: Missing declaration
- **WHEN** a readable PDF has usable topic and paragraph structure but lacks either declaration
- **THEN** extraction proceeds and its outcome includes a standards-declaration warning

#### Scenario: Declared standards
- **WHEN** a PDF declares PDF/A and PDF/UA
- **THEN** the declaration does not by itself establish either conformance or extractability

### Requirement: Per-submission extraction failures
The system SHALL report a failed extraction with the filename and an actionable
reason when a PDF is unreadable or cannot be mapped to usable topic and
paragraph structure. A failed extraction SHALL NOT be presented as a grade.

#### Scenario: Unreadable submission
- **WHEN** a PDF is corrupt, inaccessible, or cannot provide readable text
- **THEN** its outcome is a failure with a reason and no extracted units

#### Scenario: Missing usable structure
- **WHEN** the system cannot reliably associate readable text with headings and paragraphs
- **THEN** the submission is reported as an extraction failure rather than silently accepting invented structure

### Requirement: Batch outcome reporting
The system SHALL continue processing other submissions after an individual
extraction failure and SHALL record each filename's outcome and warnings in
the run result without including student text. For evaluated submissions the
run result SHALL also record each criterion result's output filename or a
safe failure reason, never criterion content.

#### Scenario: Mixed batch
- **WHEN** a batch contains both usable and unusable submissions and processing completes
- **THEN** the result lists successes, failures, and warnings, and the CLI exits successfully

#### Scenario: Batch-wide failure
- **WHEN** the batch cannot complete because of a run-level error
- **THEN** the CLI exits nonzero and reports the error

#### Scenario: Criterion results recorded by filename
- **WHEN** criterion evaluation produces per-submission result files
- **THEN** the run result lists each result's filename or failure reason and contains no findings, quotes, or student text

### Requirement: Student data stays local
The system SHALL provide a Git-ignored local location for student PDFs and
extracted material and SHALL keep automated test fixtures free of student
content. Batch execution SHALL keep extracted student text in job-local storage.

#### Scenario: Local development
- **WHEN** student PDFs or extracted text are stored in the documented local data directory
- **THEN** Git ignores those files

#### Scenario: Roihu batch results
- **WHEN** the batch exports extraction outcomes
- **THEN** exported metadata contains no extracted student text
