# Siivilä

Siivilä (Finnish for _sieve_) analyzes student PDF submissions against predefined,
versioned criteria and produces an evidence-based report for the teacher.

For each criterion the system identifies and counts evidence, locates and quotes
the relevant passages exactly, reports missing required content and citation
issues, and flags uncertain findings for teacher review.

**Siivilä never assigns grades or rubric points. The teacher makes the final
assessment.**

> The model proposes findings, deterministic software validates them, the golden
> set measures their quality, and the teacher makes the grading decision.

## How it works

```
PDF submissions
  ↓
Text and structure extraction
  ↓
LangGraph workflow → direct vLLM inference
  ↓
Pydantic validation
  ↓
Per-criterion JSON
  ↓
Markdown report → optional PDF
```

- Each criterion is evaluated separately, using LLMs for semantic judgments and
  deterministic code for reference matching, citation numbering, evidence
  validation, and report generation.
- Model output is constrained by Pydantic schemas; quotes are reconstructed from
  source text, never trusted from the model verbatim.
- A teacher-verified golden set (evaluated with Inspect AI) is the basis for
  model and prompt selection and for regression testing.
- Student text is treated as untrusted input: the model has no tools, no
  network access, no grading authority, and no access to other submissions.

## Technology stack

- **uv** — dependencies, lock file, packaging, CLI execution
- **vLLM** — direct local and Roihu inference (offline Python API, no API server)
- **Pydantic** — input and output contracts
- **LangGraph** — workflow orchestration, retries, branching, aggregation
- **Inspect AI** — golden-set evaluation and regression testing
- **Pandoc + Typst** — optional Markdown-to-PDF conversion

## Processing strategy

A typical submission contains nine topics and roughly 9,000 Finnish words. The
production model is configured for approximately 64K context, but documents are
processed mainly by topic:

- **Topic-level calls** — synthesis, source use, reflection, exercise findings,
  unsupported claims
- **Document-level aggregation** — overall coverage, cross-topic findings,
  reference consistency

Sections are defined by Typst-generated PDF headings, not arbitrary token
chunks. Input files should be PDF/A UA-1 compliant; submissions missing
those declarations are still processed, with a warning in the run manifest.

Extraction (pypdf) reads each submission into heading-aligned topics,
ordered paragraphs, and sentences with exact offsets into the canonical
extracted text, source page references, and deterministic versioned
identifiers (`topic-N`, `par-N`, `sent-N`, scoped to the submission
filename). A submission that cannot be parsed or mapped to heading
structure is recorded in the manifest with a safe failure reason — the
batch continues and still exits successfully. The manifest contains
filenames, per-file outcomes, and warnings only: never extracted text.

## Criterion design

Each criterion is evaluated separately. Initial criteria:

- synthesis of separate facts or sources _(implemented: v1.0 in `src/siivila/criteria.py`)_
- conversation with sources
- findings from required exercises (listed in course config)
- in-depth treatment of weekly themes (listed in course config)
- factual claims without references
- use of the official course book (from course config, if applicable)

Each criterion has a versioned definition containing what qualifies, what does
not qualify, required course metadata, allowed output labels, uncertainty rules,
and the expected Pydantic schema.

Each criterion produces an independent result file (`<stem>.<criterion>.json`
in `--output-dir`), shaped like:

```json
{
  "submission_id": "filename-something.pdf",
  "criterion_id": "synthesis",
  "criterion_version": "1.0",
  "status": "met",
  "instances": [
    {
      "sentence_ids": ["sent-42", "sent-43"],
      "quotes": [
        "First exact sentence span from the submission.",
        "Second exact sentence span from the submission."
      ],
      "classification": "synthesis",
      "rationale": "Connects two sources to form a broader conclusion.",
      "uncertain": false
    }
  ],
  "warnings": []
}
```

## Environments

The same CLI, schemas, prompts, workflow, and reporting code run in both
environments:

- **Local development** — macOS (Apple Silicon, 32 GB), small Apple
  Silicon-compatible model, unit / integration / smoke tests, Langfuse-style
  LLM observability for debugging.
- **Production** — Slurm batch job on CSC Roihu (NVIDIA GH200, 96 GB GPU),
  production model loaded directly with vLLM, additional GPUs for parallel
  evaluation.

## Usage

Local development (MLX backend via mlx-lm, a dev-only dependency):

```bash
uv run grade \
  --backend mlx \
  --model-path mlx-community/Qwen3.5-9B-MLX-4bit \
  --input-dir submissions \
  --output-dir results \
  --course-config course_configs/course-a.yaml
```

Production on Roihu (vLLM backend; no uv — the batch job runs the repo-root
[grade.py](grade.py) with the scratch venv's interpreter):

```bash
srun /scratch/project_1234/venv-siivila/bin/python grade.py \
  --backend vllm \
  --model-path /scratch/project_1234/vllm-models/production-model \
  --input-dir "$TMPDIR/submissions" \
  --output-dir "$TMPDIR/results" \
  --course-config course_configs/course-a.yaml
```

### Production setup (CSC Roihu)

One-time environment setup on Roihu (no uv — pip into the scratch venv):

```bash
module load pytorch
python -m venv --system-site-packages /scratch/project_1234/venv-siivila
export PIP_CACHE_DIR=/scratch/project_1234/pip-cache   # keep $HOME clean
/scratch/project_1234/venv-siivila/bin/pip install pydantic pyyaml pypdf
# Check what the pytorch module already provides, install only the rest:
/scratch/project_1234/venv-siivila/bin/python -c "import torch, vllm" \
  || /scratch/project_1234/venv-siivila/bin/pip install vllm
```

Submit the batch job (see the header of [slurm/grade.slurm](slurm/grade.slurm)
for all configuration variables):

```bash
sbatch slurm/grade.slurm                 # single GPU
sbatch --gres=gpu:4 slurm/grade.slurm    # more GPUs for parallel evaluation
```

## Evaluation and testing

- **Unit tests** (`uv run pytest tests/unit`) run without a model using
  synthetic PDF and sentence fixtures. Keep tests minimal — less is better.
- **Local smoke tests** run `uv run grade` with a small local model to verify
  system operation (model loading, batching, structured output, validation and
  retry, end-to-end JSON output) — not grading quality. Pass any unversioned
  PDF directory via `--input-dir` (e.g. under `testdata/local/`) and an output
  directory via `--output-dir`; all code and helpers stay in Git.
- **Golden-set evaluation** runs production candidates on Roihu with Inspect AI,
  measuring: schema-valid output rate; criterion precision/recall/F1; evidence
  precision/recall; span or sentence overlap; invalid evidence rate; near-miss
  false positives; prompt-injection resistance; per-criterion regressions.

The golden set is teacher-verified: each case is a submission + versioned
criterion + expected JSON. The teacher may start from an initial model result
but must be able to remove false positives, add missed evidence, correct
evidence boundaries, confirm negative findings, and mark uncertain cases.

## Prompt-injection protection (extension)

All student text is untrusted data. The model has no tools or network access,
no grading authority, no access to other submissions, and no secrets in its
context. The application isolates criterion calls, constrains output with
Pydantic, rejects unknown sentence identifiers, reconstructs quotes from source
text, ignores model-produced grades, flags suspicious instructions (e.g.
"ignore the rubric"), and includes adversarial examples in tests.

## Data protection

Student PDFs and extracted text are never committed to Git. For local
development and smoke tests, keep unversioned input PDFs and output directories
under `testdata/local/`, which is Git-ignored; all code lives in the repository.
The ignore rule is a safeguard,
not a guarantee: it does not protect against `git add -f`, and files stored
anywhere else are not covered — always check `git status` before committing.
On Roihu, all
PDFs, extracted text, caches, logs, and raw outputs stay in job-local `$TMPDIR`
and are deleted when the job ends; only validated, intentionally retained
results and reports — metadata and filenames, not student content — are
exported. Model weights are read-only from
`/scratch/project_1234/vllm-models/`; the Python environment lives in
`/scratch/project_1234/venv-siivila/` with a custom pip cache outside `$HOME`.
Persistent LangGraph checkpoints are disabled in batch jobs.

For real student data (post fake-data stage), the Slurm job will clone/pull the
public repo and download PDFs via a temporary pre-signed URL (e.g. AWS S3 or
Cloudflare R2) with TTL-based deletion.

## Roadmap

Development proceeds in small phases, each proposed, implemented, and archived
as its own OpenSpec change (see [CONTRIBUTE.md](CONTRIBUTE.md)). One phase at
a time; later phases are detailed only when reached.

1. uv project, CLI, direct vLLM backend, and Slurm script
   _done: `openspec/changes/archive/2026-11-14-add-cli-vllm-scaffold`_
2. PDF extraction and stable topic, paragraph, and sentence identifiers  
   _done: `openspec/changes/archive/2026-11-15-add-pdf-extraction`_
3. The synthesis criterion end to end
   _done: `openspec/changes/archive/2026-11-15-add-synthesis-criterion`_
4. Pydantic validation and deterministic evidence reconstruction
5. Initial golden-set annotations and Inspect AI evaluation
6. Coverage and source-engagement criteria
7. Citation, course-book, and IEEE checks
8. Deterministic Markdown and PDF reporting
9. Expanded adversarial and regression tests

## Development

See [CONTRIBUTE.md](CONTRIBUTE.md) for the development setup and the OpenSpec
spec-driven workflow (`/openspec-propose` → `/openspec-apply-change` →
`/openspec-archive-change`) that all feature work follows.
