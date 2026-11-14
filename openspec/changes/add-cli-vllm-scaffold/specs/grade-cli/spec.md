# Spec Delta

## Purpose

Defines the `grade` command-line interface through which teachers and batch jobs run evidence analysis of student submissions, identically in local development and on CSC Roihu.

## ADDED Requirements

### Requirement: CLI entry point
The system SHALL provide a `grade` command runnable via `uv run grade` that starts the analysis pipeline.

#### Scenario: Invoking the CLI with all required arguments
- **WHEN** the user runs `uv run grade --model-path <path> --input-dir <dir> --output-dir <dir> --course-config <file>` with valid arguments
- **THEN** the system loads the model, processes the submissions in the input directory, and writes results to the output directory

#### Scenario: Help output
- **WHEN** the user runs `uv run grade --help`
- **THEN** the system prints usage documentation describing every argument and exits with code 0

### Requirement: Required arguments
The CLI SHALL require `--model-path`, `--input-dir`, `--output-dir`, and `--course-config`, and SHALL fail fast with a non-zero exit code and a clear error message when any is missing or invalid.

#### Scenario: Missing required argument
- **WHEN** the user runs the CLI without `--course-config`
- **THEN** the system exits with a non-zero code and an error naming the missing argument

#### Scenario: Nonexistent input directory
- **WHEN** the user passes an `--input-dir` that does not exist
- **THEN** the system exits with a non-zero code before loading the model, with an error naming the invalid path

#### Scenario: Invalid course config
- **WHEN** the `--course-config` file is missing, unparsable, or fails schema validation
- **THEN** the system exits with a non-zero code and reports the validation error

### Requirement: Environment parity
The same CLI, arguments, and exit behavior SHALL run unchanged in local development (macOS, Apple Silicon) and in production (CSC Roihu via Slurm), with environment differences expressed only through argument values and environment variables.

#### Scenario: Same command on both environments
- **WHEN** a Slurm job and a local developer invoke the CLI with equivalent arguments
- **THEN** both invocations execute the same workflow code path, differing only in model path and directories

### Requirement: Course configuration file
The CLI SHALL load course configuration from a YAML file validated against a schema; the configuration SHALL be able to list required exercises, weekly themes, and the official course book for use by later criteria.

#### Scenario: Valid course config loads
- **WHEN** the `--course-config` points to a YAML file conforming to the schema
- **THEN** the system parses it and makes its values available to the pipeline

#### Scenario: Config missing a required field
- **WHEN** the course config omits a schema-required field
- **THEN** the system exits with a non-zero code naming the missing field
