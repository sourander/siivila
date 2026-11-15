"""Unit tests for the course config contract. No model required."""

from pathlib import Path

import pytest
import yaml

from siivila.config import CourseConfigError, load_course_config

VALID = {
    "course_name": "Example Course",
    "required_exercises": ["Exercise 1", "Exercise 2"],
    "weekly_themes": ["Theme A", "Theme B"],
    "course_book": {"title": "Course Book", "authors": ["A. Author"]},
}


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "course.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def test_valid_config_loads(tmp_path):
    config = load_course_config(_write(tmp_path, VALID))
    assert config.course_name == "Example Course"
    assert config.course_book is not None
    assert config.course_book.title == "Course Book"


def test_course_book_is_optional(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "course_book"}
    config = load_course_config(_write(tmp_path, data))
    assert config.course_book is None


@pytest.mark.parametrize("missing", ["course_name", "required_exercises", "weekly_themes"])
def test_missing_required_field_fails(tmp_path, missing):
    data = {k: v for k, v in VALID.items() if k != missing}
    with pytest.raises(CourseConfigError, match=missing):
        load_course_config(_write(tmp_path, data))


def test_empty_exercise_list_fails(tmp_path):
    data = {**VALID, "required_exercises": []}
    with pytest.raises(CourseConfigError, match="required_exercises"):
        load_course_config(_write(tmp_path, data))


def test_unknown_field_fails(tmp_path):
    data = {**VALID, "typo_field": "oops"}
    with pytest.raises(CourseConfigError, match="typo_field"):
        load_course_config(_write(tmp_path, data))


def test_missing_file_fails(tmp_path):
    with pytest.raises(CourseConfigError, match="not found"):
        load_course_config(tmp_path / "nope.yaml")


def test_unparsable_yaml_fails(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text(":\n  - [unclosed", encoding="utf-8")
    with pytest.raises(CourseConfigError, match="not valid YAML"):
        load_course_config(path)


def test_non_mapping_yaml_fails(tmp_path):
    path = tmp_path / "list.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(CourseConfigError, match="failed validation"):
        load_course_config(path)


def test_example_course_a_loads():
    example = Path(__file__).parents[2] / "course_configs" / "course-a.yaml"
    config = load_course_config(example)
    assert config.course_name
    assert len(config.required_exercises) >= 1
    assert len(config.weekly_themes) >= 1
