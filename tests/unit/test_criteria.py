"""Unit tests for the synthesis criterion v1.0 module."""

import pytest
from pydantic import ValidationError

from siivila.criteria import (
    SYNTHESIS_CRITERION_ID,
    SYNTHESIS_CRITERION_VERSION,
    SYNTHESIS_DEFINITION,
    CriterionResult,
    SynthesisInstance,
    TopicFinding,
    TopicSynthesisOutput,
    aggregate_status,
    build_submission_prompts,
    evaluate_submission,
    sentence_lookup,
    validate_findings,
)
from siivila.extraction import Paragraph, Sentence, SubmissionExtraction, Topic


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


def test_schemas_validate_hand_written_examples():
    assert "qualifies" in SYNTHESIS_DEFINITION
    assert "does not qualify" in SYNTHESIS_DEFINITION

    topic_out = TopicSynthesisOutput.model_validate(
        {
            "findings": [
                {
                    "sentence_ids": ["sent-1", "sent-2"],
                    "classification": "synthesis",
                    "rationale": "Connects two observations.",
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
            "criterion_id": SYNTHESIS_CRITERION_ID,
            "criterion_version": SYNTHESIS_CRITERION_VERSION,
            "status": "met",
            "instances": [
                {
                    "sentence_ids": ["sent-1", "sent-2"],
                    "quotes": ["Alpha first sentence.", "Alpha second sentence."],
                    "classification": "synthesis",
                    "rationale": "Connects two observations.",
                    "uncertain": False,
                }
            ],
            "warnings": [],
        }
    )
    assert result.status == "met"
    assert result.criterion_id == "synthesis"
    assert result.criterion_version == "1.0"

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

    prompts_a = build_submission_prompts(ext_a)
    assert len(prompts_a) == 2
    assert SYNTHESIS_DEFINITION in prompts_a[0]
    assert "AlphaUnique Topic One" in prompts_a[0]
    assert "sent-1: AlphaUnique first sentence." in prompts_a[0]
    assert "sent-2: AlphaUnique second sentence." in prompts_a[0]
    assert "sent-3" not in prompts_a[0]
    assert "sent-3: AlphaUnique third sentence." in prompts_a[1]
    for prompt in prompts_a:
        assert "BetaSecret" not in prompt
        assert "sub-b.pdf" not in prompt


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
    instances, warnings = validate_findings(findings, lookup)
    assert len(instances) == 1
    assert instances[0].sentence_ids == ["sent-1", "sent-2"]
    assert instances[0].quotes == ["Alpha first sentence.", "Alpha second sentence."]
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
    res = evaluate_submission(
        ext,
        [
            TopicSynthesisOutput(findings=[
                TopicFinding(sentence_ids=["sent-2"], rationale="Borderline", uncertain=True)
            ]),
            TopicSynthesisOutput(findings=[]),
        ],
    )
    assert res.status == "uncertain"
    assert len(res.instances) == 1
    assert res.instances[0].uncertain is True
