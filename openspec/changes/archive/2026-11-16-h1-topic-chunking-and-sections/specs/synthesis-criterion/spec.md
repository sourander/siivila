# Spec Delta

## MODIFIED Requirements

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
