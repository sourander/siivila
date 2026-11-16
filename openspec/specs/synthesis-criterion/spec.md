# synthesis-criterion Specification

## Purpose

Evaluates the versioned synthesis criterion (synthesis of separate facts or
sources) on each extracted submission and produces a validated per-criterion
JSON result whose evidence quotes come from source text, never from the model.

## Requirements

### Requirement: Versioned criterion definition
Each criterion SHALL have a versioned YAML definition in `criteria/*.yaml` validated against a strict schema (`id`, `version`, `qualifies`, `does_not_qualify`). Changing a definition SHALL bump its version. The `synthesis` criterion (v1.1) SHALL require comparing or integrating distinct methods, sources, or cross-topic concepts and SHALL exclude single-concept explanations, exercise-step narration, and unsubstantiated self-report.

#### Scenario: Definition drives evaluation
- **WHEN** a criterion is loaded from `criteria/*.yaml` and evaluated
- **THEN** the prompt and output validation follow that file's versioned `qualifies` and `does_not_qualify` rules

#### Scenario: Result carries the version
- **WHEN** a criterion result is written
- **THEN** it records the criterion identifier and the version from its YAML definition

#### Scenario: Invalid criterion YAML fails fast
- **WHEN** a file in `criteria/*.yaml` is missing a required field or contains unknown fields
- **THEN** loading fails with a validation error naming the file and field before model loading

### Requirement: Topic-level criterion evaluation
The system SHALL evaluate the criterion with one schema-constrained model
call per non-empty top-level (`H1`) content topic of a successfully extracted
submission, through the existing in-process backend protocol. Each topic prompt
SHALL include that topic's subheadings, paragraph structure, sentences with
their identifiers, and any extracted bibliography entries cited in that topic.

#### Scenario: Each topic is evaluated
- **WHEN** a submission extracts successfully with multiple top-level topics
- **THEN** the model is called once per topic that contains at least one sentence, skipping empty topics, and every call validates against the criterion output schema

#### Scenario: Subheadings, paragraphs, and cited references appear in prompt
- **WHEN** a topic contains subheadings, multiple paragraphs, and numeric citations matching extracted bibliography entries
- **THEN** the constructed prompt includes the subheading titles, paragraph groupings, sentence identifiers, and the matching bibliography entries

#### Scenario: Model sees only one submission
- **WHEN** criterion prompts are constructed
- **THEN** each prompt contains sentences and references from a single submission and no other student text

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

### Requirement: Course-parameterized criterion placeholders
A criterion definition MAY reference course configuration fields (`{required_exercises}`, `{weekly_themes}`, `{course_book}`). The system SHALL interpolate present values from the loaded course configuration into the criterion prompt and SHALL skip evaluating any criterion that references an optional course configuration field whose value is absent.

#### Scenario: Course values interpolated into prompt
- **WHEN** a criterion definition contains `{required_exercises}` or `{weekly_themes}`
- **THEN** the generated topic prompt includes the corresponding values from the active course configuration

#### Scenario: Criterion skipped when optional course field is absent
- **WHEN** a criterion definition references `{course_book}` and the course configuration omits `course_book`
- **THEN** the system skips that criterion for the run without recording a failure
