# Spec Delta

## Purpose

Defines how the analysis CLI is executed as a Slurm batch job on CSC Roihu, including the data-protection rules that confine student data to job-local storage.

## ADDED Requirements

### Requirement: Slurm batch script
The project SHALL provide a Slurm batch script that runs `uv run grade` on a CSC Roihu GH200 node, and the script SHALL support additional GPUs for parallel evaluation to reduce wall-clock time.

#### Scenario: Submitting a job
- **WHEN** the user submits the batch script with `sbatch` on Roihu
- **THEN** the job allocates a GH200 node, loads the production model, and runs the CLI to completion

#### Scenario: Job failure surfaces in logs
- **WHEN** the CLI exits with a non-zero code inside the job
- **THEN** the Slurm job fails and the error is visible in the job's output log

### Requirement: Job-local data confinement
The batch job SHALL keep all PDFs, extracted text, caches, logs, and raw model outputs in `$TMPDIR` (job-local storage) and SHALL NOT write student data to `$HOME`, project directories, or any persistent shared filesystem.

#### Scenario: Data stays in TMPDIR
- **WHEN** the job processes submissions
- **THEN** all intermediate artifacts (PDFs, extracted text, caches, raw outputs) exist only under `$TMPDIR`

#### Scenario: Cleanup at job end
- **WHEN** the job ends, successfully or not
- **THEN** job-local data under `$TMPDIR` is removed and nothing student-identifying persists on the node

### Requirement: Controlled result export
The job SHALL export only intentionally retained, validated results and reports — containing metadata and filenames, not student content — to the project application directory.

#### Scenario: Exporting results
- **WHEN** the job completes successfully
- **THEN** only the validated result JSON files and generated reports are copied out of `$TMPDIR` to the designated results location

### Requirement: Isolated Roihu Python environment
The job SHALL use a dedicated virtual environment under `/scratch/project_1234/venv-siivila/` (built on `module load pytorch` when system packages suffice) with a custom pip cache location, and SHALL NOT install packages into `$HOME`.

#### Scenario: Home directory untouched
- **WHEN** the job environment is created or the job runs
- **THEN** no packages or caches are written to the user's `$HOME` on Roihu

### Requirement: No persistent workflow checkpoints
The job SHALL disable persistent LangGraph checkpoints so that no workflow state containing student data survives the job.

#### Scenario: Checkpointing disabled
- **WHEN** the LangGraph workflow runs inside the batch job
- **THEN** no checkpoint data is written to persistent storage
