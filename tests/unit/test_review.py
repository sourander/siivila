"""Unit tests for review mode discovery, evidence CRUD, and CLI validation."""

import json
from pathlib import Path

import pytest

import siivila.review as review
from siivila.criteria import CriterionResult
from siivila.extraction import Paragraph, Sentence, SubmissionExtraction, Topic


def _sample_extraction(name: str = "sub-a.pdf") -> SubmissionExtraction:
    p1_text = "First sentence. Second sentence."
    s1_end = len("First sentence.")
    s2_start = s1_end + 1
    p2_text = "Third sentence."
    return SubmissionExtraction(
        submission=name,
        extraction_version="1.1",
        topics=[
            Topic(
                id="topic-1",
                title="Topic One",
                pages=[1],
                paragraphs=[
                    Paragraph(
                        id="par-1",
                        text=p1_text,
                        pages=[1],
                        sentences=[
                            Sentence(id="sent-1", start=0, end=s1_end, pages=[1]),
                            Sentence(
                                id="sent-2", start=s2_start, end=len(p1_text), pages=[1]
                            ),
                        ],
                    ),
                    Paragraph(
                        id="par-2",
                        text=p2_text,
                        pages=[1],
                        subheading="Sub 1.1",
                        sentences=[
                            Sentence(id="sent-3", start=0, end=len(p2_text), pages=[1]),
                        ],
                    ),
                ],
            )
        ],
    )


def test_resolve_pdf_dir_from_manifest_and_override(tmp_path: Path):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    (out_dir / "manifest.json").write_text(
        json.dumps({"input_dir": str(pdf_dir)}), encoding="utf-8"
    )
    assert review.resolve_pdf_dir(out_dir) == pdf_dir

    override_dir = tmp_path / "override"
    override_dir.mkdir()
    assert review.resolve_pdf_dir(out_dir, override_dir) == override_dir


def test_discover_review_targets_finds_stems_and_criteria(tmp_path: Path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    res = CriterionResult(
        submission_id="diary-1.pdf",
        criterion_id="custom_crit",
        criterion_version="2.0",
        status="not_met",
    )
    (out_dir / "diary-1.custom_crit.json").write_text(
        res.model_dump_json(), encoding="utf-8"
    )
    stems, criteria = review.discover_review_targets(out_dir)
    assert "diary-1" in stems
    assert criteria["custom_crit"] == "2.0"
    assert "synthesis" in criteria


def test_save_and_delete_instance_reconstructs_quotes_and_updates_status(
    tmp_path: Path,
):
    extraction = _sample_extraction("sub-a.pdf")
    res = review.load_or_init_result(tmp_path, "sub-a", "synthesis", "1.1")
    assert res.status == "not_met"

    # Add instance with reverse-ordered sentence IDs; must sort to document order
    res = review.save_instance(
        tmp_path,
        res,
        extraction,
        sentence_ids=["sent-3", "sent-1"],
        rationale="Connects first and third.",
        uncertain=True,
    )
    assert res.status == "uncertain"
    assert len(res.instances) == 1
    assert res.instances[0].sentence_ids == ["sent-1", "sent-3"]
    assert res.instances[0].quotes == ["First sentence.", "Third sentence."]

    # Update existing instance to confirmed and change sentences
    res = review.save_instance(
        tmp_path,
        res,
        extraction,
        sentence_ids=["sent-2"],
        rationale="Confirmed synthesis.",
        uncertain=False,
        index=0,
    )
    assert res.status == "met"
    assert len(res.instances) == 1
    assert res.instances[0].sentence_ids == ["sent-2"]
    assert res.instances[0].quotes == ["Second sentence."]
    assert res.instances[0].rationale == "Confirmed synthesis."

    # Verify persisted on disk
    reloaded = review.load_or_init_result(tmp_path, "sub-a", "synthesis", "1.1")
    assert reloaded.status == "met"
    assert len(reloaded.instances) == 1

    # Delete instance
    res = review.delete_instance(tmp_path, res, 0)
    assert res.status == "not_met"
    assert res.instances == []
    assert review.load_or_init_result(tmp_path, "sub-a", "synthesis", "1.1").instances == []


def test_cli_nonexistent_dir_fails_with_usage_error(
    tmp_path: Path, monkeypatch, capsys
):
    monkeypatch.setattr(
        review,
        "run_ui",
        lambda *_args, **_kwargs: pytest.fail("run_ui must not be called"),
    )
    code = review.main(["--dir", str(tmp_path / "missing")])
    assert code == review.EXIT_USAGE_ERROR
    assert "--dir" in capsys.readouterr().err
