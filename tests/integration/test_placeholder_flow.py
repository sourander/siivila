"""Integration test: full CLI flow with the fake backend. No model required."""

from pathlib import Path

import pytest
import yaml

import siivila.cli as cli
from siivila.backends import FakeBackend
from siivila.pipeline import HealthCheck, load_manifest

CONFIG = {
    "course_name": "Example Course",
    "required_exercises": ["Exercise 1"],
    "weekly_themes": ["Theme A"],
}


@pytest.fixture
def workspace(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    input_dir = tmp_path / "submissions"
    input_dir.mkdir()
    for name in ["student-b.pdf", "student-a.pdf"]:
        (input_dir / name).write_bytes(b"%PDF-1.4 fake\n")
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
    assert load_manifest(output_dir / "manifest.json").submissions == []
