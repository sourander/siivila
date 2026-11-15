"""Integration test: full CLI flow with the fake backend. No model required."""

from pathlib import Path

import pytest
import yaml

import siivila.cli as cli
from siivila.backends import BackendError, FakeBackend
from siivila.pipeline import HealthCheck, load_manifest
from tests.synthetic_pdf import (
    XMP_BOTH,
    DrawnLine,
    OutlineEntry,
    build_pdf,
)

CONFIG = {
    "course_name": "Example Course",
    "required_exercises": ["Exercise 1"],
    "weekly_themes": ["Theme A"],
}


def _synthetic_submission(path: Path, topic: str) -> None:
    """A minimal but genuinely extractable synthetic submission."""
    build_pdf(
        path,
        [[
            DrawnLine(topic, y=770, size=11.0),
            DrawnLine("Body line one.", y=746.0),
            DrawnLine("Body line two.", y=731.0),
            DrawnLine("Body line three.", y=716.0),
        ]],
        outline=[OutlineEntry(topic, page=0, y=770.0)],
        xmp=XMP_BOTH,
    )


@pytest.fixture
def workspace(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    input_dir = tmp_path / "submissions"
    input_dir.mkdir()
    for name in ["student-b.pdf", "student-a.pdf"]:
        _synthetic_submission(input_dir / name, topic=f"Topic of {name}")
    config = tmp_path / "course.yaml"
    config.write_text(yaml.safe_dump(CONFIG), encoding="utf-8")
    output_dir = tmp_path / "results"
    return model, input_dir, output_dir, config


def test_end_to_end_manifest(workspace, monkeypatch):
    model, input_dir, output_dir, config = workspace
    fake = FakeBackend(
        responder=lambda _p, schema: schema(operational=True, message="ready")
    )
    monkeypatch.setattr(cli, "default_backend", lambda _args: fake)

    code = cli.main([
        "--model-path", str(model),
        "--input-dir", str(input_dir),
        "--output-dir", str(output_dir),
        "--course-config", str(config),
    ])

    assert code == 0
    manifest = load_manifest(output_dir / "manifest.json")
    assert manifest.course_name == "Example Course"
    assert manifest.submissions == ["student-a.pdf", "student-b.pdf"]
    assert manifest.health_check == HealthCheck(operational=True, message="ready")
    assert manifest.created_at.tzinfo is not None
    # exactly one schema-constrained health-check call happened
    assert fake.calls == [(cli.run.__globals__["HEALTH_CHECK_PROMPT"], HealthCheck)]


def test_empty_input_dir_still_writes_manifest(workspace, monkeypatch, tmp_path):
    model, _input_dir, output_dir, config = workspace
    empty = tmp_path / "empty"
    empty.mkdir()
    fake = FakeBackend(
        responder=lambda _p, schema: schema(operational=True, message="ready")
    )
    monkeypatch.setattr(cli, "default_backend", lambda _args: fake)

    code = cli.main([
        "--model-path", str(model),
        "--input-dir", str(empty),
        "--output-dir", str(output_dir),
        "--course-config", str(config),
    ])

    assert code == 0
    manifest = load_manifest(output_dir / "manifest.json")
    assert manifest.submissions == []
    assert manifest.outcomes == []


def _run_cli(workspace, monkeypatch, input_dir):
    model, _input, output_dir, config = workspace
    fake = FakeBackend(
        responder=lambda _p, schema: schema(operational=True, message="ready")
    )
    monkeypatch.setattr(cli, "default_backend", lambda _args: fake)
    code = cli.main([
        "--model-path", str(model),
        "--input-dir", str(input_dir),
        "--output-dir", str(output_dir),
        "--course-config", str(config),
    ])
    return code, output_dir


def test_extraction_outcomes_in_manifest(workspace, monkeypatch):
    """Both synthetic submissions extract successfully."""
    _model, input_dir, _output, _config = workspace
    code, output_dir = _run_cli(workspace, monkeypatch, input_dir)
    assert code == 0
    manifest = load_manifest(output_dir / "manifest.json")
    assert manifest.extraction_version
    assert [o.filename for o in manifest.outcomes] == manifest.submissions
    assert all(o.status == "success" for o in manifest.outcomes)
    assert all(o.failure_reason is None for o in manifest.outcomes)


def test_mixed_batch_succeeds_and_lists_outcomes(workspace, monkeypatch, tmp_path):
    _model, input_dir, _output, _config = workspace
    (input_dir / "student-c-corrupt.pdf").write_bytes(b"not a pdf at all\n")

    code, output_dir = _run_cli(workspace, monkeypatch, input_dir)

    assert code == 0
    manifest = load_manifest(output_dir / "manifest.json")
    by_name = {o.filename: o for o in manifest.outcomes}
    assert by_name["student-a.pdf"].status == "success"
    assert by_name["student-b.pdf"].status == "success"
    corrupt = by_name["student-c-corrupt.pdf"]
    assert corrupt.status == "failure"
    assert corrupt.failure_code == "unreadable-pdf"
    assert corrupt.failure_reason


def test_all_failed_batch_still_succeeds(workspace, monkeypatch, tmp_path):
    model, _input, output_dir, config = workspace
    broken = tmp_path / "broken"
    broken.mkdir()
    for name in ["one.pdf", "two.pdf"]:
        (broken / name).write_bytes(b"garbage\n")

    code, out = _run_cli((model, None, output_dir, config), monkeypatch, broken)

    assert code == 0
    manifest = load_manifest(out / "manifest.json")
    assert len(manifest.outcomes) == 2
    assert all(o.status == "failure" for o in manifest.outcomes)


def test_manifest_contains_no_extracted_text(workspace, monkeypatch, tmp_path):
    """Exported metadata must not contain student/extracted content."""
    _model, input_dir, _output, _config = workspace
    code, output_dir = _run_cli(workspace, monkeypatch, input_dir)
    assert code == 0
    raw = (output_dir / "manifest.json").read_text(encoding="utf-8")
    # Fixture body text must not leak into exported metadata.
    assert "Body line" not in raw
    # No extracted-content field anywhere in the manifest.
    manifest = load_manifest(output_dir / "manifest.json")
    assert not hasattr(manifest, "extraction")
    for outcome in manifest.outcomes:
        assert set(outcome.model_dump()) == {
            "filename", "status", "warnings", "failure_code", "failure_reason",
        }


def test_run_level_error_exits_nonzero(workspace, monkeypatch, tmp_path):
    """A backend failure during the run is a run-level error: exit nonzero."""
    model, input_dir, output_dir, config = workspace

    def failing(_prompt, _schema):
        raise BackendError("model exploded")

    monkeypatch.setattr(cli, "default_backend", lambda _args: FakeBackend(failing))
    code = cli.main([
        "--model-path", str(model),
        "--input-dir", str(input_dir),
        "--output-dir", str(output_dir),
        "--course-config", str(config),
    ])
    assert code == 1
    assert not (output_dir / "manifest.json").exists()
