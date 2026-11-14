# Design

## Context

The repo is a bare `uv` scaffold (`pyproject.toml` with a `siivila` entry point, empty `src/siivila/`). The handoff (`handoff.md`) fixes the technology choices — uv, direct vLLM inference, Pydantic, LangGraph, Inspect AI, Pandoc+Typst — and the two execution environments: macOS Apple Silicon (32 GB, small model) for development, and CSC Roihu (GH200, 96 GB GPU, Slurm) for production. This change implements phase 1 of the roadmap in README.md only. Constraint from the user: network access is currently limited (train), so implementation must avoid large downloads; the vLLM install and model downloads happen later on Roihu or off-train.

## Goals / Non-Goals

**Goals:**
- A runnable `uv run grade` CLI that validates inputs, loads course config, initializes the vLLM backend, and executes a placeholder inference flow end to end.
- A thin inference-backend layer so unit/smoke tests can substitute a fake backend without loading a model.
- A reusable Slurm batch script encoding the Roihu data-protection rules (`$TMPDIR` confinement, controlled export, cleanup).
- Optional Langfuse tracing for local debugging, off by default.

**Non-Goals:**
- PDF extraction, sentence/topic identifiers, any criterion evaluation, evidence validation, reporting (later changes per the roadmap in README.md).
- Golden-set / Inspect AI evaluation.
- The S3/R2 temporary-URL download pipeline for real student PDFs (handoff defers it until real data is used; fake data is fine until then).
- Multi-GPU parallelism beyond what the Slurm script parameterizes.

## Decisions

### Direct vLLM offline API behind a small backend protocol
Use `vllm.LLM` (offline inference) directly, per the handoff — no OpenAI-compatible server, no SSH tunnel. Wrap it behind a minimal `InferenceBackend` protocol (e.g. `generate(prompts, schema) -> outputs`) so that:
- unit tests run with a fake backend (handoff: "unit tests run without a model");
- the later LangGraph workflow depends on the protocol, not on vLLM specifics.

**Alternative:** calling `vllm.LLM` inline in the CLI — rejected; it would make the "no model in unit tests" requirement impossible and couple orchestration to vLLM.

### stdlib argparse for the CLI
The CLI has four options and no subcommands yet; `argparse` covers this with zero added dependencies. Typer/click were considered and rejected for now to keep the dependency footprint small (limited bandwidth); migrating later is cheap because argument parsing is isolated in one module.

### Course config as YAML validated by a Pydantic model
`course_configs/course-a.yaml`-style files parsed into a Pydantic model listing required exercises, weekly themes, and the optional official course book. Pydantic is already a mandated dependency and gives the fail-fast validation the CLI spec requires. JSON Schema export of the config model can come later if teachers hand-edit configs.

### Placeholder pipeline flow
For this change the pipeline does: validate args → load course config → scan `--input-dir` for PDFs (listing only, no parsing) → initialize backend → run one schema-constrained health-check completion → write a run manifest JSON (arguments, discovered files, timestamp, backend info) to `--output-dir`. This proves model loading, structured output, and I/O wiring without implementing any real criterion.

### Optional Langfuse via environment variables
Observability activates only when Langfuse environment variables are set; otherwise the code path is a no-op and the package is an optional (extra) dependency, so Roihu installs need not include it.

### Roihu environment: venv with `--system-site-packages` on top of `module load pytorch`
Create `/scratch/project_1234/venv-siivila/` with `python -m venv --system-site-packages` after `module load pytorch`, so CUDA-enabled torch/vLLM builds from the module are reused and only missing packages are pip-installed. Set `PIP_CACHE_DIR` (and `UV_CACHE_DIR`) to a `/scratch` path to avoid filling the `$HOME` quota. Model weights are read-only from `/scratch/project_1234/vllm-models/`.

### Slurm script as a parameterized template
One `slurm/grade.slurm` script with `#SBATCH` directives (GH200 partition, GPU count as a variable for parallel evaluation) that:
1. clones or `git pull`s the public repo into `$TMPDIR`;
2. copies input PDFs into `$TMPDIR` (fake-data stage: from a known scratch location; the pre-signed URL pipeline is deferred);
3. activates the scratch venv and runs `uv run grade` with all work dirs under `$TMPDIR`;
4. exports only validated result JSON / reports to the project application dir;
5. removes job-local data via a `trap ... EXIT` so cleanup also runs on failure.

**Alternative:** a persistent results database — rejected for now; the handoff specifies exporting only intentionally retained results, and plain files suffice at this stage.

## Risks / Trade-offs

- **vLLM on Apple Silicon is CPU-only/experimental (no Metal/CUDA GPU support), and GH200 nodes are aarch64+CUDA** → Treat local vLLM as a smoke-test runtime with a small model; production correctness/perf validated on Roihu. If local vLLM install proves unworkable, the backend protocol allows a temporary local stand-in without touching the specs.
- **vLLM install size conflicts with the current limited bandwidth** → Implementation proceeds code-first with unit tests against the fake backend; `uv add vllm` and smoke tests with a real model are deferred until bandwidth allows (still within this change's tasks).
- **Roihu module contents unknown (`module load pytorch` may or may not ship vLLM)** → The Slurm/venv docs include a verification step; missing packages are pip-installed into the scratch venv. Recheck when Roihu access is available.
- **Trap-based cleanup could delete data needed for debugging a failed job** → Log the error to the job's Slurm output (persistent, no student content) before cleanup; opt-out env var keeps `$TMPDIR` for a debug session.
- **argparse choice may need revisiting** when later changes add subcommands (e.g., `grade eval`) → argument parsing is isolated in one module to keep that migration trivial.

## Migration Plan

Greenfield — nothing to migrate. Rollback is `git revert`; no data or external systems are affected. Roihu setup steps (venv, model download) are documented in the Slurm script header and validated on first job submission.

## Open Questions

- Which production model and which small local model to pin (decided when downloads are feasible; does not affect specs or tasks).
- Langfuse self-hosted vs. cloud for local observability (affects only env var values).
