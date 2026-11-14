"""Course configuration contract.

The course config tells the criteria what a submission is expected to
contain: which exercises must show findings, which weekly themes must be
treated in depth, and which official course book (if any) is referenced.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CourseBook(BaseModel):
    """The official course book, when the course has one."""

    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[str] = Field(default_factory=list)
    edition: str | None = None


class CourseConfig(BaseModel):
    """Schema for course_configs/*.yaml files."""

    model_config = ConfigDict(extra="forbid")

    course_name: str
    required_exercises: list[str] = Field(min_length=1)
    weekly_themes: list[str] = Field(min_length=1)
    course_book: CourseBook | None = None


class CourseConfigError(Exception):
    """Raised when a course config file is missing, unparsable, or invalid."""


def load_course_config(path: Path) -> CourseConfig:
    """Load and validate a course config YAML file.

    Raises CourseConfigError with a message naming the problem.
    """
    if not path.is_file():
        raise CourseConfigError(f"course config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CourseConfigError(f"course config is not valid YAML: {path}: {exc}") from exc
    try:
        return CourseConfig.model_validate(raw)
    except ValidationError as exc:
        raise CourseConfigError(f"course config failed validation: {path}:\n{exc}") from exc
