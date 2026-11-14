# Tasks

## 1. Project and dependencies

- [ ] 1.1 Add runtime dependencies to `pyproject.toml` (`pydantic`, `pyyaml`; `langfuse` as an optional extra) and verify `uv lock` resolves without downloading large packages
- [ ] 1.2 Add the `grade` script entry point (`grade = "siivila.cli:main"`) and verify `uv run grade --help` exits 0 and documents all four arguments

## 2. Course configuration

- [ ] 2.1 Implement the Pydantic course-config model (required exercises, weekly themes, optional official course book) and verify unit tests cover a valid config and each missing/invalid required field
- [ ] 2.2 Create `course_configs/course-a.yaml` example matching the schema and verify it loads in a unit test

## 3. CLI

- [ ] 3.1 Implement argument parsing and validation (`--model-path`, `--input-dir`, `--output-dir`, `--course-config`) using stdlib argparse and verify unit tests cover missing arguments, nonexistent `--input-dir`, and invalid config (each exits non-zero with a naming error)
- [ ] 3.2 Wire config loading into the CLI so validation failures exit before any model work and verify with a unit test asserting the backend is never constructed on invalid input

## 4. Inference backend

- [ ] 4.1 Define the `InferenceBackend` protocol (`generate(prompts, schema) -> outputs`) and a fake in-memory backend, and verify unit tests exercise the fake without loading any model
- [ ] 4.2 Implement the vLLM backend (`vllm.LLM` offline API, ~64K context for production, schema-constrained generation, bounded retry on validation failure) and verify its import/initialization logic is unit-testable with vLLM mocked out

## 5. Placeholder pipeline

- [ ] 5.1 Implement the placeholder flow (scan `--input-dir` for PDFs, run one schema-constrained health-check completion, write run manifest JSON to `--output-dir`) and verify an integration test with the fake backend produces a valid manifest
- [ ] 5.2 Add optional Langfuse tracing activated only when its environment variables are set and verify unit tests cover both the enabled path (mocked client) and the default no-op path

## 6. Slurm batch execution

- [ ] 6.1 Write `slurm/grade.slurm` (GH200 node, repo clone/pull into `$TMPDIR`, scratch venv activation, `uv run grade` with all dirs under `$TMPDIR`, GPU count parameterizable) and verify `sbatch --test-only` (or manual review, if Roihu access is unavailable) accepts the script
- [ ] 6.2 Add result export (only validated result JSON/reports to the project application dir) and `trap`-based `$TMPDIR` cleanup with a debug opt-out, and verify by dry-running the script locally with a stubbed `sbatch` environment
- [ ] 6.3 Document the Roihu setup in the script header and README (venv under `/scratch/project_1234/venv-siivila/` with `--system-site-packages`, custom `PIP_CACHE_DIR`/`UV_CACHE_DIR`, `module load pytorch` verification step) and verify the documented commands match the script

## 7. Deferred smoke validation (requires bandwidth)

- [ ] 7.1 `uv add vllm` and lock; verify install succeeds locally (CPU) or document the blocker if Apple Silicon install fails
- [ ] 7.2 Run the CLI end to end locally with a small model against fake PDFs and verify the manifest is written and structured output validates

## Workflow follow-up

- Archive the change after review requirements are satisfied.
- Verify the archived result.
