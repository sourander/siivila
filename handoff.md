# Handoff: Automated Evidence Analysis of Student Work

This process will use OpenSpec as SDD framework. Use the proposals and other as defined in the spec.

## Goal

Build a self-contained Python application that analyzes student PDF submissions against predefined criteria and produces an evidence-based Markdown or PDF report.

The system will:

- identify and count evidence for each criterion;
- locate relevant passages and quote them exactly;
- identify missing required content;
- report citation and referencing issues;
- flag uncertain findings for teacher review.

It will **not assign grades or rubric points**. The teacher makes the final assessment.

## Environments

### Local development

- MacBook Pro M2 Max with 32 GB unified memory
- Small Apple Silicon-compatible model
- Used for unit, integration, and smoke testing
- There local calls should have LLM Observability for debugging. Maybe LangFuse.

### Production

- Slurm batch job on CSC Roihu
- NVIDIA GH200 with 96 GB GPU memory
- Production model loaded directly with vLLM
- Additional GPUs may be used for parallel evaluation (for speed)

The same CLI, schemas, prompts, workflow, and reporting code run in both environments.

## Architecture

```
PDF submissions
  ↓
Text and structure extraction
  ↓
LangGraph workflow

Direct vLLM inference
  ↓
Pydantic validation
  ↓
Per-criterion JSON
  ↓
Markdown report
  ↓
Optional PDF
```

The application calls vLLM directly from Python. It does **not** depend on an OpenAI-compatible API.

## Technology choices

- **uv:** dependencies, lock file, packaging, and CLI execution
- **vLLM:** direct local and Roihu inference
- **Pydantic:** input and output contracts
- **LangGraph:** workflow orchestration, retries, branching, and aggregation
- **Inspect AI:** golden-set evaluation and regression testing
- **Pandoc + Typst:** optional Markdown-to-PDF conversion

## Command-line interface

The main command should be:

```bash
uv run grade
 --model-path /scratch/project_1234/vllm-models/production-model
 --input-dir "$TMPDIR/submissions"
 --output-dir "$TMPDIR/results"
 --course-config course_configs/course-a.yaml
```

## Processing strategy

A typical submission contains nine topics and approximately 9,000 Finnish words.

Configure the production model for approximately **64K context**, but process documents mainly by topic:

- topic-level calls for synthesis, source use, reflection, exercise findings, and unsupported claims;
- document-level aggregation for overall coverage, cross-topic findings, and reference consistency.

Use Typst-generated PDF headings to define sections rather than arbitrary token chunks. The input files should be PDF/A UA-1 comliant.

## Criterion design

Evaluate each criterion separately. Initial criteria include:

- synthesis of separate facts or sources;
- conversation with sources;
- findings from required exercises (listed in course config);
- in-depth treatment of weekly themes (listed in course config);
- factual claims without references;
- use of the official course book (from course config, if applicable);

Each criterion should have a versioned definition containing:

- what qualifies;
- what does not qualify;
- required course metadata;
- allowed output labels;
- uncertainty rules;
- expected Pydantic schema.

Use LLMs for semantic judgments and deterministic code for reference matching, citation numbering, evidence validation, and report generation.

## Results

Each criterion produces an independent result. Below is a draft idea of what it might look like:

```
{
 "submission_id": "filename-something.pdf",
 "criterion_id": "synthesis",
 "criterion_version": "1.0",
 "status": "met",
 "instances": [
  {
   "sentence_ids": ["topic-3-s42", "topic-3-s43"],
   "classification": "synthesis",
   "rationale": "Connects two sources to form a broader conclusion."
  }
 ],
 "warnings": []
}


```

## (Extension) Prompt-injection protection

Treat all student text as untrusted data.

The model has:

- no tools or network access;
- no grading authority;
- no access to other submissions;
- no secrets in its context.

The application must:

- isolate criterion calls;
- constrain output with Pydantic;
- reject unknown sentence identifiers;
- reconstruct quotes from source text;
- ignore model-produced grades;
- flag suspicious instructions such as “ignore the rubric”;
- include adversarial examples in tests.

## Golden set

The golden set is the basis for model and prompt selection.

Each test case consists of: submission + versioned criterion + teacher-verified expected JSON

The teacher may use an initial model result as a starting point but must be able to:

- remove false positives;
- add missed evidence;
- correct evidence boundaries;
- confirm negative findings;
- mark uncertain cases.

## Testing

### Unit tests

Run without a model: uv run pytest tests/unit

Test PDF extraction, sectioning, sentence IDs, schemas, citation parsing, quote reconstruction, and report generation. Avoid overdoing tests. Less is better.

### Local smoke tests

Use a small model on the Mac to test:

- model loading;
- batching;
- structured output;
- LangGraph routing;
- validation and retry behavior;
- end-to-end report creation.

These tests verify system operation, not grading quality.

### Golden-set evaluation

Run production candidates on Roihu using Inspect AI.

Measure:

- schema-valid output rate;
- criterion precision, recall, and F1;
- evidence precision and recall;
- span or sentence overlap;
- invalid evidence rate;
- near-miss false positives;
- prompt-injection resistance;
- regressions by criterion.

## Data protection

On Roihu:

- read model weights from `/scratch/project_1234/vllm-models/`;
- if packages are needed that are not in `module load pytorch`, we will create a new venv into `/scratch/project_1234/venv-siivila/` with system dependencies and custom PIP cache location to avoid overcrowding home dir.
- keep PDFs, extracted text, caches, logs, and raw outputs in `$TMPDIR`;
- the PDFs will never be stored to GitHub. When running the process the Slurm job will clone the public repository from Github (or git pull), and then download the PDF data using self-signed URI from e.g. AWS S3 or CloudFlare R2. The URL should be temporary. The data should have TTL deletion. This pipeline will be developed when we move from fake data to actual user data.
- disable persistent LangGraph checkpoints;
- export only intentionally retained validated results and reports; There contain only metadata and filenames and can be stored into project application dir.
- delete job-local data when the job ends.

## Implementation order

Start small! Do not try to implement too much at a time.

1. Create the `uv` project, CLI, direct vLLM backend, and Slurm script.
2. Implement PDF extraction and stable topic, paragraph, and sentence identifiers.
3. Implement the synthesis criterion end to end.
4. Add Pydantic validation and deterministic evidence reconstruction.
5. Create initial golden-set annotations and Inspect AI evaluation.
6. Add coverage and source-engagement criteria.
7. Add citation, course-book, and IEEE checks.
8. Add deterministic Markdown and PDF reporting.
9. Expand adversarial and regression tests.

## Core decisions

- One self-contained project and CLI
- Direct vLLM inference, with no API server or SSH tunnel
- Pydantic for durable contracts
- LangGraph for orchestration
- Inspect AI for golden-set evaluation
- Separate evaluation for each criterion
- Teacher-verified expected results
- Deterministic evidence validation
- Reports provide evidence, never grades

> **The model proposes findings, deterministic software validates them, the golden set measures their quality, and the teacher makes the grading decision.**
