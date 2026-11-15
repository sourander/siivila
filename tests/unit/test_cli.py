"""Unit tests for CLI argument validation and ordering. No model required."""

from pathlib import Path

import pytest
import yaml

import siivila.cli as cli

VALID_CONFIG = {
    "course_name": "Example Course",
    "required_exercises": ["Exercise 1"],
    "weekly_themes": ["Theme A"],
}


@pytest.fixture
def paths(tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    config = tmp_path / "course.yaml"
    config.write_text(yaml.safe_dump(VALID_CONFIG), encoding="utf-8")
    return model, input_dir, tmp_path / "out", config


def _argv(model, input_dir, output_dir, config):
    return [
        "--model-path", str(model),
        "--input-dir", str(input_dir),
        "--output-dir", str(output_dir),
        "--course-config", str(config),
    ]


def test_missing_required_argument_exits_nonzero_and_names_it(paths, capsys):
    model, input_dir, output_dir, _config = paths
    argv = _argv(model, input_dir, output_dir, _config)
    argv = argv[: argv.index("--course-config")]  # drop the last required arg
    with pytest.raises(SystemExit) as excinfo:
        cli.main(argv)
    assert excinfo.value.code != 0
    assert "--course-config" in capsys.readouterr().err


def test_nonexistent_input_dir_fails_before_backend(paths, monkeypatch, capsys):
    model, _input_dir, output_dir, config = paths
    monkeypatch.setattr(
        cli, "create_backend",
        lambda *_args, **_kwargs: pytest.fail("backend must not be constructed"),
    )
    code = cli.main(_argv(model, paths[1] / "missing", output_dir, config))
    assert code != 0
    assert "--input-dir" in capsys.readouterr().err


def test_unloadable_model_path_fails_with_clear_error(paths, capsys):
    """vLLM treats --model-path as a directory; a missing one fails fast."""
    _model, input_dir, output_dir, config = paths
    argv = _argv(input_dir / "no-model", input_dir, output_dir, config)
    argv += ["--backend", "vllm"]
    code = cli.main(argv)
    assert code != 0
    assert "model path does not exist" in capsys.readouterr().err


def test_invalid_course_config_fails_before_backend(paths, monkeypatch, capsys):
    model, input_dir, output_dir, config = paths
    config.write_text(yaml.safe_dump({"course_name": "missing the rest"}), encoding="utf-8")
    monkeypatch.setattr(
        cli, "create_backend",
        lambda *_args, **_kwargs: pytest.fail("backend must not be constructed"),
    )
    code = cli.main(_argv(model, input_dir, output_dir, config))
    assert code != 0
    assert "required_exercises" in capsys.readouterr().err
