"""Placeholder analysis pipeline.

Proves the scaffold end to end — config loaded, backend initialized,
schema-constrained generation working, results written — before any real
criterion evaluation exists (later roadmap phases).
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from .backends import ModelBackend
from .config import CourseConfig
from .observability import trace_span

HEALTH_CHECK_PROMPT = (
    "You are the Siivilä analysis pipeline performing a health check. "
    "Confirm that you are operational."
)


class HealthCheck(BaseModel):
    """Schema-constrained health-check response."""

    operational: bool
    message: str


class RunManifest(BaseModel):
    """What a run saw and did. Metadata and filenames only — no content."""

    course_name: str
    model_path: str
    input_dir: str
    output_dir: str
    course_config: str
    submissions: list[str]
    health_check: HealthCheck
    created_at: datetime


def find_submissions(input_dir: Path) -> list[Path]:
    """List PDF submissions in the input directory (no parsing yet)."""
    return sorted(input_dir.glob("*.pdf"))


def run(args, config: CourseConfig, backend: ModelBackend) -> int:
    """Execute the placeholder flow and write the run manifest."""
    submissions = find_submissions(args.input_dir)

    with trace_span("health-check"):
        health_check = backend.generate([HEALTH_CHECK_PROMPT], HealthCheck)[0]

    manifest = RunManifest(
        course_name=config.course_name,
        model_path=str(args.model_path),
        input_dir=str(args.input_dir),
        output_dir=str(args.output_dir),
        course_config=str(args.course_config),
        submissions=[path.name for path in submissions],
        health_check=health_check,
        created_at=datetime.now(UTC),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")

    print(
        f"grade: {len(submissions)} submission(s) found, "
        f"health check operational={health_check.operational}, "
        f"manifest written to {manifest_path}"
    )
    return 0


def load_manifest(path: Path) -> RunManifest:
    return RunManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
