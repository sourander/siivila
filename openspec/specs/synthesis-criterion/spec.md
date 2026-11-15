# synthesis-criterion Specification

## Purpose

Evaluates the versioned synthesis criterion (synthesis of separate facts or
sources) on each extracted submission and produces a validated per-criterion
JSON result whose evidence quotes come from source text, never from the model.

## Requirements

### Requirement: Versioned criterion definition
The synthesis criterion SHALL have a versioned definition stating what
qualifies as synthesis, what does not qualify, and the output schema the
model must produce. Changing the definition SHALL bump its version.

#### Scenario: Definition drives evaluation
- **WHEN** the criterion is evaluated
- **THEN** the prompt and output validation follow the current versioned definition

#### Scenario: Result carries the version
- **WHEN** a criterion result is written
- **THEN** it records the criterion identifier and the version used

### Requirement: Topic-level criterion evaluation
The system SHALL evaluate the criterion with one schema-constrained model
call per topic of a successfully extracted submission, through the existing
in-process backend protocol. The model receives only that topic's sentences
with their identifiers.

#### Scenario: Each topic is evaluated
- **WHEN** a submission extracts successfully with multiple topics
- **THEN** the model is called once per topic and every call validates against the criterion output schema

#### Scenario: Model sees only one submission
- **WHEN** criterion prompts are constructed
- **THEN** each prompt contains sentences from a single submission and no other student text

### Requirement: Deterministic evidence validation
The system SHALL validate every finding's sentence identifiers against the
submission's extraction and SHALL reject identifiers that do not resolve.
Quotes in the result SHALL be the exact extracted sentence spans.

#### Scenario: Unknown sentence identifier
- **WHEN** a model finding references a sentence identifier not present in the submission
- **THEN** that finding is rejected and a warning is recorded

#### Scenario: Quote reconstruction
- **WHEN** a finding is accepted
- **THEN** its quoted text is the exact span of each referenced sentence in the extracted paragraph text

### Requirement: Per-criterion result output
The system SHALL write one criterion result JSON per evaluated submission to
the output directory, containing status, validated findings, and warnings.
The result SHALL NOT contain a grade or rubric points.

#### Scenario: Result written for successful submission
- **WHEN** criterion evaluation completes for a submission
- **THEN** a result JSON with the submission filename, criterion id and version, status, findings, and warnings exists in the output directory

#### Scenario: Uncertain findings flagged
- **WHEN** the model marks a finding as uncertain
- **THEN** the result keeps it flagged for teacher review rather than dropping or confirming it

### Requirement: Per-submission criterion failures
A submission whose criterion evaluation fails (for example schema-invalid
model output after bounded retries) SHALL be recorded with a safe failure
reason. The batch SHALL continue and the CLI SHALL still exit successfully.

#### Scenario: One submission's evaluation fails
- **WHEN** the model cannot produce valid criterion output for one submission
- **THEN** that submission's outcome records a failure reason without student text, other submissions are still evaluated, and the run exits successfully

#### Scenario: Failed extraction is not evaluated
- **WHEN** a submission's extraction failed
- **THEN** no criterion call is made for it and its criterion outcome records the extraction failure
