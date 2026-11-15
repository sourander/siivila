# Proposal

## Why

Criterion definitions require the most human iteration, but `synthesis` is currently hardcoded as a Python string inside `src/siivila/criteria.py` and its v1.0 wording is so broad ("combining two facts, observations, or concepts") that the model flags routine exercise narration, single-concept explanations, and learning-diary "pseudo-wisdoms" as synthesis. Moving criterion definitions into human-editable YAML files in `criteria/*.yaml` and tightening `synthesis` to v1.1 separates teacher-authored rubrics from the generic evaluation engine before more criteria are added.

## What Changes

- Load versioned criterion definitions (`id`, `version`, `qualifies`, `does_not_qualify`) from `criteria/*.yaml`, validated with Pydantic (`extra="forbid"`) using the same YAML loader pattern as `course_configs/*.yaml`.
- Generalize `src/siivila/criteria.py` and `src/siivila/pipeline.py` so the prompt builder, output schema, quote reconstruction, and pipeline loop work for any loaded `CriterionConfig` rather than hardcoding `synthesis`.
- Support standard Python `{field}` placeholders from `CourseConfig` (`{required_exercises}`, `{weekly_themes}`, `{course_book}`) in criterion bullets, and automatically skip a criterion when it references an optional course config field that is `None` (such as `{course_book}`).
- Add `criteria/synthesis.yaml` (version `1.1`) with tightened `qualifies` and `does_not_qualify` rules that explicitly exclude single-concept textbook explanations, lab/parameter step narration, and unsubstantiated meta-commentary ("pseudo-wisdom").

## Capabilities

### New Capabilities

<!-- None -->

### Modified Capabilities

- `synthesis-criterion`: Criterion definitions are loaded from `criteria/*.yaml` (with optional `CourseConfig` placeholder interpolation and automatic skipping when an optional course field is absent), and `synthesis` is updated to v1.1 to reject pseudo-wisdoms, lab narration, and single-concept explanations.

## Impact

- **Config**: New `criteria/synthesis.yaml` (v1.1) at repository root alongside `course_configs/`.
- **Code**: `src/siivila/criteria.py` (add `CriterionConfig` + loader, remove hardcoded synthesis strings, interpolate `CourseConfig` fields), `src/siivila/pipeline.py` (evaluate loaded criteria per submission), `src/siivila/cli.py` (fail fast if `criteria/` is invalid).
- **Tests**: Update `tests/unit/test_criteria.py` for YAML-loaded criteria, placeholder interpolation/skipping, and `synthesis` v1.1.
- **Dependencies**: None added (`pyyaml` and `pydantic` are already installed).
