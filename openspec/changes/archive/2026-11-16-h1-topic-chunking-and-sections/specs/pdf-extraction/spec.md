# Spec Delta

## MODIFIED Requirements

### Requirement: Structured submission extraction
The system SHALL extract readable text from supported Finnish and English
Typst-template PDFs into an ordered hierarchy of top-level (`H1`) topics,
paragraphs, and sentences. Topic boundaries SHALL follow top-level document
outline headings rather than arbitrary text chunks or nested subheadings, and
nested subheadings SHALL be recorded on the paragraphs they precede without
being emitted as paragraph text.

#### Scenario: Headings and paragraphs are available
- **WHEN** a readable submission contains usable heading and paragraph structure
- **THEN** its extracted content preserves topic order, paragraph order, and sentence order

#### Scenario: Nested subheadings grouped under top-level topic
- **WHEN** a top-level outline heading contains nested subheadings in the document outline
- **THEN** all paragraphs under those subheadings belong to the enclosing top-level topic, carry their subheading title, and exclude the subheading line itself from sentence spans

#### Scenario: Multiple headings share a page
- **WHEN** two topic headings occur on the same page
- **THEN** content is assigned to the appropriate topic rather than solely by page number

#### Scenario: Paragraph continues across pages
- **WHEN** a paragraph continues across a page boundary
- **THEN** the extracted representation retains its complete text in reading order

## ADDED Requirements

### Requirement: Bibliography section extraction
The system SHALL separate a top-level bibliography section (`Lähteet` or `References`) from evaluated content topics into structured reference entries with their reference numbers, canonical text, and source page references.

#### Scenario: Finnish or English references heading
- **WHEN** a submission contains a top-level `Lähteet` or `References` heading
- **THEN** its entries are extracted into the submission's reference list with page provenance and the section is not included in `topics`

#### Scenario: Reference entry spans a page break
- **WHEN** a numbered bibliography entry is followed by another numbered entry at the top of the next page
- **THEN** each numbered entry is extracted as a separate reference item

### Requirement: Appendix exclusion
The system SHALL exclude appendix sections (`Liitteet`, `Appendices`, or top-level headings starting with `Liite` or `Appendix`) and any nested sub-sections beneath them from extracted content topics and criterion evaluation.

#### Scenario: Finnish or English appendices heading
- **WHEN** a submission contains a top-level `Liitteet`, `Appendices`, `Liite`, or `Appendix` section
- **THEN** all text under that section is excluded from extracted `topics` and `references`
