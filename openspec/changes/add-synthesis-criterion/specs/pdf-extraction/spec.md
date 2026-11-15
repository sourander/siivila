# Spec Delta

## MODIFIED Requirements

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
