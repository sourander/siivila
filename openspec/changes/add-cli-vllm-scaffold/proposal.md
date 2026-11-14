# Proposal

## Why

Siivilä analyzes student PDF submissions against predefined criteria and produces evidence-based reports for teachers, who keep final grading authority. The project is currently a bare `uv` scaffold; before any PDF extraction or criterion evaluation can exist, we need a runnable foundation: a CLI, a direct vLLM inference backend that works identically on a local MacBook and on CSC Roihu (GH200, Slurm), and a Slurm batch script to run it. This is phase 1 of the roadmap in README.md ("Start small!").

## What Changes

- Set up the `uv` project properly: dependencies (vLLM, Pydantic, LangGraph as needed for the backend), lock file, and packaging so the CLI runs via `uv run grade`.
- Add the `grade` CLI with the agreed interface: `--model-path`, `--input-dir`, `--output-dir`, `--course-config`. At this stage it validates inputs, loads the model, and runs a minimal placeholder inference flow (no PDF analysis criteria yet).
- Add a direct vLLM inference backend (Python API, `LLM` class) — **no OpenAI-compatible API server, no SSH tunnel**. The same backend code runs locally (small Apple Silicon-compatible model) and in production (GH200 via Slurm).
- Add a Slurm batch script template for CSC Roihu following the data-protection rules: model weights read from `/scratch/project_1234/vllm-models/`, all PDFs/extracted text/caches/logs/raw outputs confined to `$TMPDIR`, only intentionally retained validated results exported, job-local data deleted at job end.
- Local development observability hook (e.g., Langfuse) for debugging local LLM calls.

## Capabilities

### New Capabilities

- `grade-cli`: The `uv run grade` command-line interface — its arguments, input validation, environment parity (same CLI local and on Roihu), and exit behavior.
- `llm-inference`: Direct vLLM inference from Python (no API server), model loading from a configurable path, and structured-output support that later criteria and Pydantic validation will build on.
- `slurm-batch-execution`: Slurm batch job definition and data-handling rules for running the CLI on CSC Roihu within `$TMPDIR`, with controlled export of results.

### Modified Capabilities

(None — no existing specs.)

## Impact

- **Code**: new `src/siivila/` modules (CLI entry point, vLLM backend, config loading); `pyproject.toml` gains dependencies and the `grade` script entry point.
- **Dependencies**: vLLM, Pydantic, (optionally Langfuse for local observability). Note: vLLM is heavy and has no Apple Silicon GPU wheels — local development uses a small compatible model; installation strategy for macOS vs. Roihu (venv in `/scratch/project_1234/venv-siivila/` with custom pip cache) is decided in design.
- **Infrastructure**: new Slurm batch script template; Roihu venv and cache layout under `/scratch/project_1234/`.
- **Out of scope** (later changes): PDF extraction and stable identifiers, criterion evaluation (synthesis first), Pydantic evidence validation, golden set and Inspect AI evaluation, Markdown/PDF reporting, prompt-injection test suite.
