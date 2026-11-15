"""Analysis pipeline: extraction, criterion evaluation, health check, manifest."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .backends import ModelBackend
from .config import CourseConfig
from .criteria import (
    CriterionConfig,
    TopicSynthesisOutput,
    build_submission_prompts,
    evaluate_submission,
    is_criterion_applicable,
    load_criteria,
)
from .extraction import EXTRACTION_VERSION, ExtractionOutcome, extract_submission
from .observability import trace_span

HEALTH_CHECK_PROMPT = (
    "You are the Siivilä analysis pipeline performing a health check. "
    "Confirm that you are operational."
)

CRITERION_FAILURE_REASON = "criterion evaluation failed"


class HealthCheck(BaseModel):
    """Schema-constrained health-check response."""

    operational: bool
    message: str


class SubmissionOutcome(BaseModel):
    """Per-file extraction outcome. Safe to export: no student content."""

    filename: str
    status: Literal["success", "failure"]
    warnings: list[str] = Field(default_factory=list)
    failure_code: str | None = None
    failure_reason: str | None = None


class CriterionOutcome(BaseModel):
    """Per-submission criterion outcome. Filenames and safe reasons only."""

    filename: str
    criterion_id: str = "synthesis"
    result_file: str | None = None
    failure_reason: str | None = None


class RunManifest(BaseModel):
    """What a run saw and did. Metadata and filenames only — no content."""

    course_name: str
    model_path: str
    input_dir: str
    output_dir: str
    course_config: str
    submissions: list[str]
    extraction_version: str
    outcomes: list[SubmissionOutcome]
    criterion_results: list[CriterionOutcome] = Field(default_factory=list)
    health_check: HealthCheck
    created_at: datetime


def find_submissions(input_dir: Path) -> list[Path]:
    """List PDF submissions in the input directory."""
    return sorted(input_dir.glob("*.pdf"))


def run(
    args,
    config: CourseConfig,
    backend: ModelBackend,
    criteria: list[CriterionConfig] | None = None,
) -> int:
    """Extract and evaluate all submissions and write the run manifest.

    Per-file extraction and criterion failures are recorded, not raised: a
    completed batch exits successfully even when some (or all) submissions
    fail. Run-level errors (config, backend health check) still exit nonzero
    from the CLI.
    """
    loaded_criteria = criteria if criteria is not None else load_criteria()
    active_criteria = [
        c for c in loaded_criteria if is_criterion_applicable(c, config)
    ]
    submissions = find_submissions(args.input_dir)

    extracted: list[tuple[Path, ExtractionOutcome]] = []
    outcomes: list[SubmissionOutcome] = []
    for path in submissions:
        outcome = extract_submission(path)
        extracted.append((path, outcome))
        outcomes.append(
            SubmissionOutcome(
                filename=outcome.filename,
                status=outcome.status,
                warnings=outcome.warnings,
                failure_code=outcome.failure_code,
                failure_reason=outcome.failure_reason,
            )
        )
        detail = (
            outcome.status
            if outcome.status == "success"
            else f"failure ({outcome.failure_code})"
        )
        suffix = f", {len(outcome.warnings)} warning(s)" if outcome.warnings else ""
        print(f"grade: {outcome.filename}: {detail}{suffix}")

    with trace_span("health-check"):
        health_check = backend.generate([HEALTH_CHECK_PROMPT], HealthCheck)[0]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    criterion_results: list[CriterionOutcome] = []
    for path, outcome in extracted:
        for criterion in active_criteria:
            if outcome.status != "success" or outcome.extraction is None:
                criterion_results.append(
                    CriterionOutcome(
                        filename=outcome.filename,
                        criterion_id=criterion.id,
                        failure_reason=outcome.failure_reason or outcome.failure_code,
                    )
                )
                continue
            prompts = build_submission_prompts(
                outcome.extraction, criterion, config
            )
            try:
                with trace_span(f"criterion-{criterion.id}"):
                    topic_outputs = (
                        backend.generate(prompts, TopicSynthesisOutput)
                        if prompts
                        else []
                    )
                result = evaluate_submission(
                    outcome.extraction, topic_outputs, criterion
                )
                result_filename = f"{path.stem}.{criterion.id}.json"
                (args.output_dir / result_filename).write_text(
                    result.model_dump_json(indent=2) + "\n", encoding="utf-8"
                )
                criterion_results.append(
                    CriterionOutcome(
                        filename=outcome.filename,
                        criterion_id=criterion.id,
                        result_file=result_filename,
                    )
                )
                print(
                    f"grade: {outcome.filename}: {criterion.id} {result.status} -> "
                    f"{result_filename}"
                )
            except Exception:
                # Never propagate raw exception details: they may embed student text.
                criterion_results.append(
                    CriterionOutcome(
                        filename=outcome.filename,
                        criterion_id=criterion.id,
                        failure_reason=CRITERION_FAILURE_REASON,
                    )
                )
                print(
                    f"grade: {outcome.filename}: {criterion.id} failure "
                    f"({CRITERION_FAILURE_REASON})"
                )

    manifest = RunManifest(
        course_name=config.course_name,
        model_path=str(args.model_path),
        input_dir=str(args.input_dir),
        output_dir=str(args.output_dir),
        course_config=str(args.course_config),
        submissions=[path.name for path in submissions],
        extraction_version=EXTRACTION_VERSION,
        outcomes=outcomes,
        criterion_results=criterion_results,
        health_check=health_check,
        created_at=datetime.now(UTC),
    )
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    succeeded = sum(1 for outcome in outcomes if outcome.status == "success")
    print(
        f"grade: {len(submissions)} submission(s) found, "
        f"{succeeded} extracted, {len(submissions) - succeeded} failed, "
        f"health check operational={health_check.operational}, "
        f"manifest written to {manifest_path}"
    )
    return 0
