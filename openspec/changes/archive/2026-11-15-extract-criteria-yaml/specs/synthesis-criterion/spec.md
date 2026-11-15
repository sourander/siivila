# Spec Delta

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Course-parameterized criterion placeholders
A criterion definition MAY reference course configuration fields (`{required_exercises}`, `{weekly_themes}`, `{course_book}`). The system SHALL interpolate present values from the loaded course configuration into the criterion prompt and SHALL skip evaluating any criterion that references an optional course configuration field whose value is absent.

#### Scenario: Course values interpolated into prompt
- **WHEN** a criterion definition contains `{required_exercises}` or `{weekly_themes}`
- **THEN** the generated topic prompt includes the corresponding values from the active course configuration

#### Scenario: Criterion skipped when optional course field is absent
- **WHEN** a criterion definition references `{course_book}` and the course configuration omits `course_book`
- **THEN** the system skips that criterion for the run without recording a failure
