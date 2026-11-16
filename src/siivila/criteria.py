"""Criterion configuration, prompt building, validation, and aggregation."""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .config import CourseConfig
from .extraction import ReferenceEntry, SubmissionExtraction, Topic

CRITERIA_DIR = Path(__file__).resolve().parents[2] / "criteria"

StatusLabel = Literal["met", "not_met", "uncertain"]

_CITATION_BRACKET_RE = re.compile(r"\[(\d+(?:\s*[;,–-]\s*\d+)*)\]")


class CriterionConfig(BaseModel):
    """Schema for criteria/*.yaml files."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    qualifies: list[str] = Field(min_length=1)
    does_not_qualify: list[str] = Field(min_length=1)


class CriterionConfigError(Exception):
    """Raised when a criterion YAML file is missing, unparsable, or invalid."""


def load_criterion(path: Path) -> CriterionConfig:
    """Load and validate a single criterion YAML file."""
    if not path.is_file():
        raise CriterionConfigError(f"criterion config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CriterionConfigError(
            f"criterion config is not valid YAML: {path}: {exc}"
        ) from exc
    try:
        return CriterionConfig.model_validate(raw)
    except ValidationError as exc:
        raise CriterionConfigError(
            f"criterion config failed validation: {path}:\n{exc}"
        ) from exc


def load_criteria(criteria_dir: Path = CRITERIA_DIR) -> list[CriterionConfig]:
    """Load and validate all criteria/*.yaml files in sorted order."""
    if not criteria_dir.is_dir():
        raise CriterionConfigError(f"criteria directory not found: {criteria_dir}")
    paths = sorted(criteria_dir.glob("*.yaml"))
    if not paths:
        raise CriterionConfigError(f"no criterion YAML files found in: {criteria_dir}")
    return [load_criterion(path) for path in paths]


def _default_criterion() -> CriterionConfig:
    return load_criterion(CRITERIA_DIR / "synthesis.yaml")


def is_criterion_applicable(
    criterion: CriterionConfig, course_config: CourseConfig | None = None
) -> bool:
    """Return False when a criterion references {course_book} and the course has none."""
    if course_config is not None and course_config.course_book is None:
        bullets = criterion.qualifies + criterion.does_not_qualify
        if any("{course_book}" in bullet for bullet in bullets):
            return False
    return True


def _interpolate(text: str, course_config: CourseConfig | None) -> str:
    if course_config is None:
        return text
    book = ""
    if course_config.course_book is not None:
        authors = ", ".join(course_config.course_book.authors)
        book = (
            f"{course_config.course_book.title} ({authors})"
            if authors
            else course_config.course_book.title
        )
    return (
        text.replace("{required_exercises}", ", ".join(course_config.required_exercises))
        .replace("{weekly_themes}", ", ".join(course_config.weekly_themes))
        .replace("{course_book}", book)
    )


def format_criterion_definition(
    criterion: CriterionConfig, course_config: CourseConfig | None = None
) -> str:
    """Render the versioned criterion header and bullet rules for a prompt."""
    qualifies = "\n".join(
        f"- {_interpolate(item, course_config)}" for item in criterion.qualifies
    )
    does_not = "\n".join(
        f"- {_interpolate(item, course_config)}" for item in criterion.does_not_qualify
    )
    return (
        f"Criterion: {criterion.id} (version {criterion.version})\n\n"
        f"What qualifies as {criterion.id}:\n{qualifies}\n\n"
        f"What does not qualify as {criterion.id}:\n{does_not}"
    )


class TopicFinding(BaseModel):
    """One model-proposed finding within a topic."""

    sentence_ids: list[str]
    classification: str = "synthesis"
    rationale: str
    uncertain: bool = False


class TopicSynthesisOutput(BaseModel):
    """Schema-constrained model output for one topic."""

    findings: list[TopicFinding] = Field(default_factory=list)


class SynthesisInstance(BaseModel):
    """Validated finding with exact quotes from extracted spans."""

    sentence_ids: list[str]
    quotes: list[str]
    classification: str = "synthesis"
    rationale: str
    uncertain: bool = False


class CriterionResult(BaseModel):
    """Per-submission criterion evaluation result."""

    submission_id: str
    criterion_id: str = "synthesis"
    criterion_version: str = "1.1"
    status: StatusLabel
    instances: list[SynthesisInstance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _cited_reference_numbers(text: str) -> set[int]:
    """Extract integer reference numbers from bracketed citations like [1], [1; 3], [9–11]."""
    cited: set[int] = set()
    for match in _CITATION_BRACKET_RE.finditer(text):
        for item in re.split(r"[;,]", match.group(1)):
            part = item.strip()
            if not part:
                continue
            range_parts = re.split(r"[–-]", part)
            if len(range_parts) == 2:
                start, end = int(range_parts[0].strip()), int(range_parts[1].strip())
                if start <= end and end - start <= 100:
                    cited.update(range(start, end + 1))
            else:
                cited.add(int(part))
    return cited


def build_topic_prompt(
    topic: Topic,
    criterion: CriterionConfig | None = None,
    course_config: CourseConfig | None = None,
    references: list[ReferenceEntry] | None = None,
) -> str:
    """Build the evaluation prompt for a single topic."""
    crit = criterion or _default_criterion()
    definition = format_criterion_definition(crit, course_config)
    lines: list[str] = []
    cited_numbers: set[int] = set()
    current_subheading: str | None = None
    for paragraph in topic.paragraphs:
        if not paragraph.sentences:
            continue
        if paragraph.subheading != current_subheading:
            current_subheading = paragraph.subheading
            if current_subheading is not None:
                lines.append(f"Subheading: {current_subheading}")
        lines.append(f"[{paragraph.id}]")
        for sentence in paragraph.sentences:
            span_text = paragraph.text[sentence.start : sentence.end]
            lines.append(f"{sentence.id}: {span_text}")
            cited_numbers.update(_cited_reference_numbers(span_text))
    body = "\n".join(lines) if lines else "(no sentences)"

    refs_block = ""
    if references and cited_numbers:
        matched = [
            f"[{ref.number}] {ref.text}"
            for ref in references
            if ref.number is not None and ref.number in cited_numbers
        ]
        if matched:
            refs_block = "\n\nReferences cited in this topic:\n" + "\n".join(matched)

    return (
        f"{definition}\n\n"
        f"Identify every passage in the topic below that demonstrates {crit.id}. "
        "Reference only the provided sentence identifiers (sent-N). "
        "Set uncertain=true when a passage is borderline and needs teacher review. "
        "Do not assign grades or points.\n"
        f'Return JSON matching: {{"findings": [{{"sentence_ids": ["sent-1", "sent-2"], '
        f'"classification": "{crit.id}", "rationale": "...", "uncertain": false}}]}} '
        '(or {"findings": []} if none).\n\n'
        f"Topic: {topic.title}\n"
        f"Sentences:\n{body}{refs_block}"
    )


def build_submission_prompts(
    extraction: SubmissionExtraction,
    criterion: CriterionConfig | None = None,
    course_config: CourseConfig | None = None,
) -> list[str]:
    """Build one prompt per non-empty topic for a submission, or [] if skipped."""
    crit = criterion or _default_criterion()
    if not is_criterion_applicable(crit, course_config):
        return []
    non_empty_topics = [
        topic
        for topic in extraction.topics
        if any(paragraph.sentences for paragraph in topic.paragraphs)
    ]
    return [
        build_topic_prompt(topic, crit, course_config, references=extraction.references)
        for topic in non_empty_topics
    ]


def sentence_lookup(extraction: SubmissionExtraction) -> dict[str, str]:
    """Map every sentence id in the submission to its exact extracted span."""
    return {
        sentence.id: paragraph.text[sentence.start : sentence.end]
        for topic in extraction.topics
        for paragraph in topic.paragraphs
        for sentence in paragraph.sentences
    }


def validate_findings(
    findings: list[TopicFinding],
    lookup: dict[str, str],
    classification: str | None = None,
) -> tuple[list[SynthesisInstance], list[str]]:
    """Reject findings with unknown sentence ids and attach exact source quotes."""
    instances: list[SynthesisInstance] = []
    warnings: list[str] = []
    for finding in findings:
        if not finding.sentence_ids:
            warnings.append("empty-sentence-ids")
            continue
        unknown = [sid for sid in finding.sentence_ids if sid not in lookup]
        if unknown:
            warnings.extend(f"unknown-sentence-id:{sid}" for sid in unknown)
            continue
        instances.append(
            SynthesisInstance(
                sentence_ids=finding.sentence_ids,
                quotes=[lookup[sid] for sid in finding.sentence_ids],
                classification=classification or finding.classification,
                rationale=finding.rationale,
                uncertain=finding.uncertain,
            )
        )
    return instances, warnings


def aggregate_status(instances: list[SynthesisInstance]) -> StatusLabel:
    """Determine overall criterion status from validated instances."""
    if any(not inst.uncertain for inst in instances):
        return "met"
    if instances:
        return "uncertain"
    return "not_met"


def evaluate_submission(
    extraction: SubmissionExtraction,
    topic_outputs: list[TopicSynthesisOutput],
    criterion: CriterionConfig | None = None,
) -> CriterionResult:
    """Validate and aggregate topic model outputs into a per-submission result."""
    crit = criterion or _default_criterion()
    lookup = sentence_lookup(extraction)
    all_findings = [
        finding for output in topic_outputs for finding in output.findings
    ]
    instances, warnings = validate_findings(
        all_findings, lookup, classification=crit.id
    )
    return CriterionResult(
        submission_id=extraction.submission,
        criterion_id=crit.id,
        criterion_version=crit.version,
        status=aggregate_status(instances),
        instances=instances,
        warnings=warnings,
    )
