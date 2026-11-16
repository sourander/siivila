# review-mode Specification

## Purpose

Provide an interactive local review interface for inspecting extracted submissions alongside per-criterion findings and adding, updating, or deleting evidence instances to produce teacher-verified golden-set files.

## Requirements

### Requirement: Review CLI launch and directory resolution
The system SHALL provide a CLI command that accepts a directory of criterion result files (`--dir`) and an optional PDF directory override (`--pdf-dir`). When `--pdf-dir` is omitted, the system SHALL resolve the PDF directory from `manifest.json` in the target directory or fall back to the target directory and its parent.

#### Scenario: Launch with valid result directory and manifest
- **WHEN** the user runs the review command with `--dir` pointing to a directory containing `manifest.json` and `<stem>.<criterion>.json`
- **THEN** the system resolves the submission PDF from `manifest.json`'s `input_dir` and starts the review interface

#### Scenario: Missing or non-existent result directory
- **WHEN** the user runs the review command with a `--dir` path that does not exist or is not a directory
- **THEN** the command exits nonzero and prints a usage error message to standard error

### Requirement: Submission and criterion selection
The system SHALL allow the user to select among submissions discovered in the target directory and among criteria present in result files or defined in `criteria/*.yaml`.

#### Scenario: Switch active criterion
- **WHEN** the user selects a criterion in the review interface
- **THEN** the interface loads the corresponding `<stem>.<criterion>.json` findings (or an empty result initialized with that criterion's version when no file exists yet) and updates the highlighted sentences

### Requirement: Full submission rendering with evidence highlights
The system SHALL render the selected submission's extracted topics, subheadings, paragraphs, sentences with their identifiers (`sent-N`), and bibliography references, and SHALL visually distinguish sentences belonging to confirmed instances, uncertain instances, and the active selection.

#### Scenario: Display submission with confirmed and uncertain findings
- **WHEN** a submission and criterion are loaded in the review interface
- **THEN** every extracted topic, paragraph, sentence, and reference entry is displayed in reading order, and sentences referenced by criterion instances are highlighted according to their certainty state

### Requirement: Evidence instance creation, editing, and deletion
The system SHALL allow the user to add a new evidence instance from selected sentence identifiers, update an existing instance's sentence identifiers, rationale, or uncertainty flag, and delete an existing instance. Every change SHALL reconstruct exact sentence quotes from the extracted submission, recompute the overall criterion status (`met`, `uncertain`, or `not_met`), and persist the updated JSON to `<stem>.<criterion>.json`.

#### Scenario: Add a new evidence instance
- **WHEN** the user selects one or more sentences, enters a rationale, and saves a new instance
- **THEN** the instance is appended with exact extracted quotes for those sentence identifiers, the overall status is updated, and `<stem>.<criterion>.json` is written to disk

#### Scenario: Update an existing evidence instance
- **WHEN** the user modifies an existing instance's selected sentences, rationale, or uncertainty flag and saves
- **THEN** the instance's sentence identifiers, reconstructed quotes, rationale, and uncertainty flag are updated in place, the overall status is recomputed, and `<stem>.<criterion>.json` is written to disk

#### Scenario: Delete an evidence instance
- **WHEN** the user deletes an existing instance
- **THEN** the instance is removed from the criterion result, the overall status is recomputed, and `<stem>.<criterion>.json` is written to disk
