# Tasks

## 1. YAML Criteria Config and Synthesis v1.1

- [x] 1.1 Create `criteria/synthesis.yaml` (version `1.1`) with the tightened `qualifies` and `does_not_qualify` lists, and add `CriterionConfig` + `load_criteria` in `src/siivila/criteria.py` using `yaml.safe_load` and `ConfigDict(extra="forbid")`; verify with unit tests in `tests/unit/test_criteria.py` covering valid loading (`criteria/synthesis.yaml`) and fast failure on invalid/missing YAML fields.
- [x] 1.2 Generalize `src/siivila/criteria.py` (`build_topic_prompt`, `build_submission_prompts`, `validate_findings`, `evaluate_submission`) to accept a `CriterionConfig` and optional `CourseConfig`, interpolate `{required_exercises}`, `{weekly_themes}`, and `{course_book}` placeholders, and skip a criterion when `{course_book}` is referenced and `course_config.course_book is None`; verify with `uv run pytest tests/unit/test_criteria.py`.

## 2. Pipeline and CLI Integration

- [x] 2.1 Update `src/siivila/pipeline.py` and `src/siivila/cli.py` to load `criteria/*.yaml` before model initialization, loop over active criteria per submission, and write `<stem>.<criterion.id>.json` Outcomes; verify with `uv run pytest` across all unit and integration tests and update `README.md` (`## Criterion design`) to reference `criteria/synthesis.yaml`.
