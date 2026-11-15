# Design

## Context

See `proposal.md` — Why. Currently, `src/siivila/criteria.py` hardcodes `SYNTHESIS_CRITERION_ID`, `SYNTHESIS_CRITERION_VERSION`, and `SYNTHESIS_DEFINITION`, while `src/siivila/config.py` loads `course_configs/*.yaml` via `yaml.safe_load` + a strict Pydantic `BaseModel(extra="forbid")`. The rest of `criteria.py` (topic prompt formatting, `sent-N` dictionary validation, quote reconstruction, and `met`/`not_met`/`uncertain` aggregation) is already generic across topic-level criteria.

## Goals / Non-Goals

**Goals:**

- Store human-authored criterion definitions as YAML files in `criteria/*.yaml` at the repository root.
- Reuse the existing `yaml.safe_load` + Pydantic `ConfigDict(extra="forbid")` pattern from `src/siivila/config.py`.
- Support course-specific placeholders (`{required_exercises}`, `{weekly_themes}`, `{course_book}`) and skip criteria referencing an omitted optional field (`course_book is None`).
- Ship `criteria/synthesis.yaml` at version `1.1` with tightened rules.

**Non-Goals:**

- No class hierarchy, plugin registry, or custom DSL for criteria.
- No new CLI flags or external templating libraries (such as Jinja2).
- No additional criteria beyond `synthesis.yaml` in this change.

## Decisions

### Top-level `criteria/*.yaml` validated by `CriterionConfig`

Criterion files live in `criteria/` alongside `course_configs/` and are loaded in sorted filename order (`sorted(criteria_dir.glob("*.yaml"))`), matching `find_submissions`. Each file validates against:

```python
class CriterionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    version: str
    qualifies: list[str] = Field(min_length=1)
    does_not_qualify: list[str] = Field(min_length=1)
```

Alternative considered: embedding criteria inside each `course_configs/*.yaml` file — rejected because all courses share the PDF Learning Diary format and duplicating criterion prompts across course files would fragment versioned definitions.

### Standard library string formatting and one-line optional skip

Course-dependent criteria reference `{required_exercises}`, `{weekly_themes}`, or `{course_book}` directly inside their `qualifies` / `does_not_qualify` bullets. Before evaluating a criterion, a helper checks whether the joined text contains `{course_book}` when `config.course_book is None`; if so, the criterion is skipped for that run. Otherwise, bullets are rendered with `.format(...)` using formatted strings from `CourseConfig`.

Alternative considered: adding `enabled` flags or `requires: [course_book]` metadata fields to `CriterionConfig` — rejected as redundant when the `{course_book}` placeholder itself already declares the dependency.

### Generic `classification` stamping in Python

In `criteria.py`, `TopicFinding` and `SynthesisInstance` (renamed/aliased cleanly) replace `Literal["synthesis"]` with `str` defaulted or stamped from `criterion.id` during `validate_findings`, so the model output schema and result JSON work unchanged for any `criterion.id`.

## Risks / Trade-offs

- [Unescaped braces in YAML criterion text break `.format()`] → Only substitute the known placeholders (`{required_exercises}`, `{weekly_themes}`, `{course_book}`) or validate formatting at config load time so syntax errors fail fast before model loading.
- [Prompt changes alter findings on existing test PDFs] → Bumping `synthesis` to `1.1` records the version boundary in `<stem>.synthesis.json`.
