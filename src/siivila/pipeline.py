"""Analysis pipeline: extraction, health check, run manifest.

Phase 2 of the roadmap: extracts every submission into traceable topics,
paragraphs, and sentences (kept in memory), runs the model health check,
and writes a metadata-only manifest with per-file extraction outcomes.
Criterion evaluation arrives in later phases.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .backends import ModelBackend
from .config import CourseConfig
from .extraction import EXTRACTION_VERSION, extract_submission
from .observability import trace_span

HEALTH_CHECK_PROMPT = (
    "You are the Siivilä analysis pipeline performing a health check. "
    "Confirm that you are operational."
)


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
    health_check: HealthCheck
    created_at: datetime


def find_submissions(input_dir: Path) -> list[Path]:
    """List PDF submissions in the input directory."""
    return sorted(input_dir.glob("*.pdf"))


def run(args, config: CourseConfig, backend: ModelBackend) -> int:
    """Extract all submissions and write the run manifest.

    Per-file extraction failures are recorded, not raised: a completed batch
    exits successfully even when some (or all) submissions fail. Run-level
    errors (config, backend) still exit nonzero from the CLI.
    """
    submissions = find_submissions(args.input_dir)

    outcomes: list[SubmissionOutcome] = []
    for path in submissions:
        outcome = extract_submission(path)
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

    manifest = RunManifest(
        course_name=config.course_name,
        model_path=str(args.model_path),
        input_dir=str(args.input_dir),
        output_dir=str(args.output_dir),
        course_config=str(args.course_config),
        submissions=[path.name for path in submissions],
        extraction_version=EXTRACTION_VERSION,
        outcomes=outcomes,
        health_check=health_check,
        created_at=datetime.now(UTC),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
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



def load_manifest(path: Path) -> RunManifest:
    return RunManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
