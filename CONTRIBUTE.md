# Contributing to Siivilä

Siivilä analyzes student PDF submissions against predefined criteria and produces evidence-based reports. It never assigns grades — the teacher makes the final assessment. The product vision, criterion design, processing strategy, and phased roadmap live in [README.md](README.md); read it first.

## Development setup

```bash
uv sync
uv run pytest tests/unit    # unit tests run without a model
```

Two environments run the same code:

- **Local** (macOS, Apple Silicon): development, unit/integration/smoke tests with a small model. Optional Langfuse tracing activates via environment variables.
- **Production** (CSC Roihu, GH200, Slurm): see `slurm/` once it exists. Model weights live read-only under `/scratch/project_1234/vllm-models/`; all student data stays in `$TMPDIR`.

**Data protection:** never commit student PDFs or extracted text to Git. Job-local data is deleted when a Slurm job ends; only validated, intentionally retained results are exported.

## Spec-driven development with OpenSpec

All feature work follows the OpenSpec cycle. Specifications are the source of truth; code implements specs, not the other way around.

### The cycle

```
explore → propose (specify + design + plan) → implement → verify → archive
```

1. **Explore** (optional) — think through a problem before committing to a change.
   Ask questions, compare options, no artifacts written.
   Skill: `/openspec-explore`

2. **Propose** — describe what you want to build. The skill creates a change under
   `openspec/changes/<change-name>/` with all planning artifacts in one step:
   - `proposal.md` — why and what (the **specify** step, at a high level)
   - `specs/<capability>/spec.md` — behavior deltas: requirements with testable
     scenarios (**specify**, in detail)
   - `design.md` — how: technical decisions, alternatives, risks (**design**)
   - `tasks.md` — ordered, verifiable implementation checklist (**plan**)

   Skill: `/openspec-propose`

3. **Implement** — work through `tasks.md`, checking off boxes as you go.
   Skill: `/openspec-apply-change`

4. **Verify** — before archiving:
   ```bash
   openspec validate "<change-name>" --strict
   uv run pytest tests/unit
   ```
   Every task box in `tasks.md` must be checked, and the specs' scenarios must
   hold against the implementation.

5. **Archive** — merge the delta specs into the main specs under
   `openspec/specs/` and move the change to the archive.
   Skill: `/openspec-archive-change`

### Keeping artifacts coherent

- Need to revise the plan mid-flight? Use `/openspec-update-change` to edit the
  change's artifacts — don't let proposal, specs, design, and tasks drift apart.
- Want the main specs updated without archiving yet? Use `/openspec-sync-specs`.

### Useful CLI commands

```bash
openspec list                      # active changes
openspec list --specs              # capability inventory
openspec status --change "<name>"  # artifact progress
openspec validate --strict         # validate everything
openspec view                      # interactive dashboard
```

## Conventions

- **Start small.** Follow the roadmap in [README.md](README.md#roadmap):
  one change per phase, reviewed and archived before the next begins.
- **One capability, one spec.** Name capabilities for durable behavior
  (`grade-cli`, `llm-inference`), not for the work item (`add-login-endpoint`).
- **LLMs for judgment, code for facts.** Semantic judgments go through the model;
  reference matching, citation numbering, evidence validation, and report
  generation are deterministic code.
- **Tests are minimal and model-free.** Unit tests must not load a model — use the
  fake inference backend. Less is better; test behavior, not implementation.
- **Student text is untrusted input.** The model has no tools, no network, no
  grading authority. Keep it that way.
