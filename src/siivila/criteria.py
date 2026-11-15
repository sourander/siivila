"""Synthesis criterion (v1.0): definition, prompt, validation, aggregation."""

from typing import Literal

from pydantic import BaseModel, Field

from .extraction import SubmissionExtraction, Topic

SYNTHESIS_CRITERION_ID = "synthesis"
SYNTHESIS_CRITERION_VERSION = "1.0"

SYNTHESIS_DEFINITION = """Criterion: synthesis (version 1.0)

What qualifies as synthesis:
- Combining, comparing, or connecting two or more separate facts, observations, concepts, or sources to form a broader conclusion, interpretation, or insight.

What does not qualify as synthesis:
- Summarizing or paraphrasing a single source or fact in isolation.
- Listing separate facts or sources next to each other without connecting them.
- Unrelated personal opinions that do not integrate facts or sources."""

StatusLabel = Literal["met", "not_met", "uncertain"]


class TopicFinding(BaseModel):
    """One model-proposed synthesis finding within a topic."""

    sentence_ids: list[str]
    classification: Literal["synthesis"] = "synthesis"
    rationale: str
    uncertain: bool = False


class TopicSynthesisOutput(BaseModel):
    """Schema-constrained model output for one topic."""

    findings: list[TopicFinding] = Field(default_factory=list)


class SynthesisInstance(BaseModel):
    """Validated synthesis finding with exact quotes from extracted spans."""

    sentence_ids: list[str]
    quotes: list[str]
    classification: Literal["synthesis"] = "synthesis"
    rationale: str
    uncertain: bool = False


class CriterionResult(BaseModel):
    """Per-submission synthesis criterion evaluation result."""

    submission_id: str
    criterion_id: str = SYNTHESIS_CRITERION_ID
    criterion_version: str = SYNTHESIS_CRITERION_VERSION
    status: StatusLabel
    instances: list[SynthesisInstance] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def build_topic_prompt(topic: Topic) -> str:
    """Build the synthesis evaluation prompt for a single topic."""
    lines = [
        f"{sentence.id}: {paragraph.text[sentence.start:sentence.end]}"
        for paragraph in topic.paragraphs
        for sentence in paragraph.sentences
    ]
    body = "\n".join(lines) if lines else "(no sentences)"
    return (
        f"{SYNTHESIS_DEFINITION}\n\n"
        "Identify every passage in the topic below that demonstrates synthesis. "
        "Reference only the provided sentence identifiers (sent-N). "
        "Set uncertain=true when a passage is borderline and needs teacher review. "
        "Do not assign grades or points.\n"
        'Return JSON matching: {"findings": [{"sentence_ids": ["sent-1", "sent-2"], '
        '"classification": "synthesis", "rationale": "...", "uncertain": false}]} '
        '(or {"findings": []} if none).\n\n'
        f"Topic: {topic.title}\n"
        f"Sentences:\n{body}"
    )


def build_submission_prompts(extraction: SubmissionExtraction) -> list[str]:
    """Build one prompt per topic for a submission."""
    return [build_topic_prompt(topic) for topic in extraction.topics]


def sentence_lookup(extraction: SubmissionExtraction) -> dict[str, str]:
    """Map every sentence id in the submission to its exact extracted span."""
    return {
        sentence.id: paragraph.text[sentence.start : sentence.end]
        for topic in extraction.topics
        for paragraph in topic.paragraphs
        for sentence in paragraph.sentences
    }


def validate_findings(
    findings: list[TopicFinding], lookup: dict[str, str]
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
                classification=finding.classification,
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
    extraction: SubmissionExtraction, topic_outputs: list[TopicSynthesisOutput]
) -> CriterionResult:
    """Validate and aggregate topic model outputs into a per-submission result."""
    lookup = sentence_lookup(extraction)
    all_findings = [
        finding for output in topic_outputs for finding in output.findings
    ]
    instances, warnings = validate_findings(all_findings, lookup)
    return CriterionResult(
        submission_id=extraction.submission,
        status=aggregate_status(instances),
        instances=instances,
        warnings=warnings,
    )
