"""Unit tests for YAML criterion configuration, prompts, validation, and aggregation."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from siivila.config import CourseBook, CourseConfig
from siivila.criteria import (
    CRITERIA_DIR,
    CriterionConfig,
    CriterionConfigError,
    CriterionResult,
    SynthesisInstance,
    TopicFinding,
    TopicSynthesisOutput,
    aggregate_status,
    build_submission_prompts,
    evaluate_submission,
    format_criterion_definition,
    is_criterion_applicable,
    load_criteria,
    load_criterion,
    sentence_lookup,
    validate_findings,
)
from siivila.extraction import Paragraph, Sentence, SubmissionExtraction, Topic

VALID_CRITERION = {
    "id": "synthesis",
    "version": "1.1",
    "qualifies": ["Comparing two sources."],
    "does_not_qualify": ["Single-concept explanation."],
}


def _sample_extraction(name: str = "sub-a.pdf", prefix: str = "Alpha") -> SubmissionExtraction:
    p1_text = f"{prefix} first sentence. {prefix} second sentence."
    s1_end = len(f"{prefix} first sentence.")
    s2_start = s1_end + 1
    p2_text = f"{prefix} third sentence."
    return SubmissionExtraction(
        submission=name,
        extraction_version="1.0",
        topics=[
            Topic(
                id="topic-1",
                title=f"{prefix} Topic One",
                pages=[1],
                paragraphs=[
                    Paragraph(
                        id="par-1",
                        text=p1_text,
                        pages=[1],
                        sentences=[
                            Sentence(id="sent-1", start=0, end=s1_end, pages=[1]),
                            Sentence(id="sent-2", start=s2_start, end=len(p1_text), pages=[1]),
                        ],
                    )
                ],
            ),
            Topic(
                id="topic-2",
                title=f"{prefix} Topic Two",
                pages=[2],
                paragraphs=[
                    Paragraph(
                        id="par-2",
                        text=p2_text,
                        pages=[2],
                        sentences=[
                            Sentence(id="sent-3", start=0, end=len(p2_text), pages=[2]),
                        ],
                    )
                ],
            ),
        ],
    )


def test_synthesis_yaml_loads_and_validates():
    criteria = load_criteria(CRITERIA_DIR)
    by_id = {c.id: c for c in criteria}
    assert "synthesis" in by_id
    syn = by_id["synthesis"]
    assert syn.version == "1.1"
    rendered = format_criterion_definition(syn)
    assert "What qualifies as synthesis:" in rendered
    assert "What does not qualify as synthesis:" in rendered
    assert "pseudo-wisdom" in rendered


@pytest.mark.parametrize("missing", ["id", "version", "qualifies", "does_not_qualify"])
def test_missing_required_criterion_field_fails_fast(tmp_path: Path, missing: str):
    data = {k: v for k, v in VALID_CRITERION.items() if k != missing}
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(CriterionConfigError, match=missing):
        load_criterion(path)


def test_unknown_or_invalid_criterion_yaml_fails_fast(tmp_path: Path):
    extra_path = tmp_path / "extra.yaml"
    extra_path.write_text(
        yaml.safe_dump({**VALID_CRITERION, "unknown_field": "nope"}), encoding="utf-8"
    )
    with pytest.raises(CriterionConfigError, match="unknown_field"):
        load_criterion(extra_path)

    bad_yaml = tmp_path / "unparsable.yaml"
    bad_yaml.write_text(":\n  - [unclosed", encoding="utf-8")
    with pytest.raises(CriterionConfigError, match="not valid YAML"):
        load_criterion(bad_yaml)

    with pytest.raises(CriterionConfigError, match="not found"):
        load_criterion(tmp_path / "missing.yaml")


def test_schemas_validate_hand_written_examples():
    topic_out = TopicSynthesisOutput.model_validate(
        {
            "findings": [
                {
                    "sentence_ids": ["sent-1", "sent-2"],
                    "classification": "synthesis",
                    "rationale": "Connects two sources.",
                    "uncertain": False,
                }
            ]
        }
    )
    assert len(topic_out.findings) == 1
    assert topic_out.findings[0].sentence_ids == ["sent-1", "sent-2"]

    result = CriterionResult.model_validate(
        {
            "submission_id": "sub-a.pdf",
            "criterion_id": "synthesis",
            "criterion_version": "1.1",
            "status": "met",
            "instances": [
                {
                    "sentence_ids": ["sent-1", "sent-2"],
                    "quotes": ["Alpha first sentence.", "Alpha second sentence."],
                    "classification": "synthesis",
                    "rationale": "Connects two sources.",
                    "uncertain": False,
                }
            ],
            "warnings": [],
        }
    )
    assert result.status == "met"
    assert result.criterion_id == "synthesis"
    assert result.criterion_version == "1.1"

    with pytest.raises(ValidationError):
        CriterionResult.model_validate(
            {
                "submission_id": "sub-a.pdf",
                "status": "invalid_status",
            }
        )


def test_prompt_builder_includes_sentence_ids_and_isolates_submission():
    ext_a = _sample_extraction("sub-a.pdf", "AlphaUnique")
    ext_b = _sample_extraction("sub-b.pdf", "BetaSecret")
    syn = load_criterion(CRITERIA_DIR / "synthesis.yaml")

    prompts_a = build_submission_prompts(ext_a, syn)
    assert len(prompts_a) == 2
    assert "Criterion: synthesis (version 1.1)" in prompts_a[0]
    assert "AlphaUnique Topic One" in prompts_a[0]
    assert "sent-1: AlphaUnique first sentence." in prompts_a[0]
    assert "sent-2: AlphaUnique second sentence." in prompts_a[0]
    assert "sent-3" not in prompts_a[0]
    assert "sent-3: AlphaUnique third sentence." in prompts_a[1]
    for prompt in prompts_a:
        assert "BetaSecret" not in prompt
        assert "sub-b.pdf" not in prompt


def test_course_placeholders_interpolated_and_optional_course_book_skipped():
    ext = _sample_extraction("sub-a.pdf", "Alpha")
    exercise_crit = CriterionConfig(
        id="required_exercises",
        version="1.0",
        qualifies=["Findings from: {required_exercises} and themes {weekly_themes}"],
        does_not_qualify=["Unrelated notes."],
    )
    book_crit = CriterionConfig(
        id="course_book",
        version="1.0",
        qualifies=["References the official book: {course_book}"],
        does_not_qualify=["No reference to {course_book}."],
    )
    course_without_book = CourseConfig(
        course_name="Course A",
        required_exercises=["Ex 1", "Ex 2"],
        weekly_themes=["Week 1"],
        course_book=None,
    )
    course_with_book = CourseConfig(
        course_name="Course B",
        required_exercises=["Ex 1"],
        weekly_themes=["Week 1"],
        course_book=CourseBook(title="Doing Data Science", authors=["O'Neil"]),
    )

    prompts = build_submission_prompts(ext, exercise_crit, course_without_book)
    assert len(prompts) == 2
    assert "Ex 1, Ex 2" in prompts[0]
    assert "Week 1" in prompts[0]

    assert not is_criterion_applicable(book_crit, course_without_book)
    assert build_submission_prompts(ext, book_crit, course_without_book) == []

    assert is_criterion_applicable(book_crit, course_with_book)
    book_prompts = build_submission_prompts(ext, book_crit, course_with_book)
    assert len(book_prompts) == 2
    assert "Doing Data Science (O'Neil)" in book_prompts[0]


def test_evidence_validation_rejects_unknown_ids_and_reconstructs_exact_quotes():
    ext = _sample_extraction("sub-a.pdf", "Alpha")
    lookup = sentence_lookup(ext)

    findings = [
        TopicFinding(
            sentence_ids=["sent-1", "sent-2"],
            rationale="Valid synthesis.",
            uncertain=False,
        ),
        TopicFinding(
            sentence_ids=["sent-1", "sent-999"],
            rationale="Hallucinated id.",
            uncertain=False,
        ),
        TopicFinding(
            sentence_ids=[],
            rationale="Empty ids.",
            uncertain=False,
        ),
    ]
    instances, warnings = validate_findings(findings, lookup, classification="synthesis")
    assert len(instances) == 1
    assert instances[0].sentence_ids == ["sent-1", "sent-2"]
    assert instances[0].quotes == ["Alpha first sentence.", "Alpha second sentence."]
    assert instances[0].classification == "synthesis"
    assert "unknown-sentence-id:sent-999" in warnings
    assert "empty-sentence-ids" in warnings


def test_status_aggregation_covers_all_three_labels():
    confirmed = SynthesisInstance(
        sentence_ids=["sent-1"],
        quotes=["Alpha first sentence."],
        rationale="Clear synthesis.",
        uncertain=False,
    )
    flagged = SynthesisInstance(
        sentence_ids=["sent-2"],
        quotes=["Alpha second sentence."],
        rationale="Borderline case.",
        uncertain=True,
    )

    assert aggregate_status([]) == "not_met"
    assert aggregate_status([flagged]) == "uncertain"
    assert aggregate_status([confirmed]) == "met"
    assert aggregate_status([flagged, confirmed]) == "met"

    ext = _sample_extraction("sub-a.pdf", "Alpha")
    custom_crit = CriterionConfig(
        id="custom_check",
        version="2.0",
        qualifies=["Qualifies."],
        does_not_qualify=["Does not qualify."],
    )
    res = evaluate_submission(
        ext,
        [
            TopicSynthesisOutput(
                findings=[
                    TopicFinding(sentence_ids=["sent-2"], rationale="Borderline", uncertain=True)
                ]
            ),
            TopicSynthesisOutput(findings=[]),
        ],
        criterion=custom_crit,
    )
    assert res.status == "uncertain"
    assert res.criterion_id == "custom_check"
    assert res.criterion_version == "2.0"
    assert len(res.instances) == 1
    assert res.instances[0].classification == "custom_check"
    assert res.instances[0].uncertain is True
