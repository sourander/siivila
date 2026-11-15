"""Command-line interface for Siivilä evidence analysis."""

import argparse
import sys
from pathlib import Path

from .backends import BackendError, create_backend
from .config import CourseConfigError, load_course_config
from .criteria import CriterionConfigError, load_criteria
from .pipeline import run

EXIT_USAGE_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grade",
        description=(
            "Analyze student PDF submissions against versioned criteria and "
            "produce evidence-based reports. Never assigns grades."
        ),
    )
    parser.add_argument(
        "--model-path",
        required=True,
        type=Path,
        help="Path to the model weights directory (local model or production model).",
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing the PDF submissions to analyze.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where results and reports are written.",
    )
    parser.add_argument(
        "--course-config",
        required=True,
        type=Path,
        help="YAML course configuration (required exercises, weekly themes, course book).",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "mlx", "vllm"],
        default="auto",
        help=(
            "Inference backend. 'auto' (default) prefers vllm and falls back "
            "to mlx-lm. An explicit choice fails if that framework is missing."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Validate everything cheap before touching the model: fail fast.
    # (Model-path validity is checked by the backend constructor, since what
    # counts as valid differs: a directory for vLLM, also a HF id for MLX.)
    if not args.input_dir.is_dir():
        print(
            f"grade: error: --input-dir does not exist or is not a directory: "
            f"{args.input_dir}",
            file=sys.stderr,
        )
        return EXIT_USAGE_ERROR
    try:
        config = load_course_config(args.course_config)
        criteria = load_criteria()
    except (CourseConfigError, CriterionConfigError) as exc:
        print(f"grade: error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        backend = create_backend(args.backend, model_path=args.model_path)
    except BackendError as exc:
        print(f"grade: error: {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR

    try:
        return run(args, config, backend, criteria=criteria)
    except BackendError as exc:
        print(f"grade: error: {exc}", file=sys.stderr)
        return 1
