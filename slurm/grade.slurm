#!/bin/bash
#===============================================================================
# siivila grade — Slurm batch job for CSC Roihu (GH200)
#
# One-time Roihu setup (no uv on Roihu — pip into the scratch venv):
#   module load pytorch
#   python -m venv --system-site-packages /scratch/project_1234/venv-siivila
#   export PIP_CACHE_DIR=/scratch/project_1234/pip-cache   # keep $HOME clean
#   /scratch/project_1234/venv-siivila/bin/pip install pydantic pyyaml
#   # Check what the pytorch module already provides, install only the rest:
#   /scratch/project_1234/venv-siivila/bin/python -c "import torch, vllm" \
#     || /scratch/project_1234/venv-siivila/bin/pip install vllm
#
# Submit:
#   sbatch slurm/grade.slurm                 # single GPU
#   sbatch --gres=gpu:4 slurm/grade.slurm    # more GPUs for parallel evaluation
#
# Configuration via environment (sbatch --export=ALL,VAR=value ...):
#   SIIVILA_REPO_URL        public repo to clone (default: GitHub origin)
#   SIIVILA_MODEL_PATH      model weights (default: production model on scratch)
#   SIIVILA_COURSE_CONFIG   course config path inside the repo
#   SIIVILA_VENV            scratch venv (default: /scratch/project_1234/venv-siivila)
#   SIIVILA_SUBMISSIONS_SRC directory containing the PDFs to analyze (required)
#   SIIVILA_RESULTS_DIR     export target for validated results (required)
#   SIIVILA_KEEP_TMPDIR     set to 1 to skip cleanup when debugging a failure
#
# Data protection: PDFs, extracted text, caches, logs, and raw model outputs
# exist only under $TMPDIR and are deleted when the job ends (trap on EXIT,
# success or failure). Only validated results — JSON and reports with
# metadata and filenames, no student content — are exported to
# $SIIVILA_RESULTS_DIR. Persistent LangGraph checkpoints are disabled.
#===============================================================================
#SBATCH --job-name=siivila-grade
#SBATCH --account=project_1234
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=siivila-grade-%j.out

set -euo pipefail

REPO_URL="${SIIVILA_REPO_URL:-https://github.com/sourander/siivila.git}"
MODEL_PATH="${SIIVILA_MODEL_PATH:-/scratch/project_1234/vllm-models/production-model}"
COURSE_CONFIG="${SIIVILA_COURSE_CONFIG:-course_configs/course-a.yaml}"
VENV="${SIIVILA_VENV:-/scratch/project_1234/venv-siivila}"
SUBMISSIONS_SRC="${SIIVILA_SUBMISSIONS_SRC:?set SIIVILA_SUBMISSIONS_SRC to the directory containing the PDFs}"
RESULTS_DIR="${SIIVILA_RESULTS_DIR:?set SIIVILA_RESULTS_DIR to the results export directory}"

JOB_ID="${SLURM_JOB_ID:-local}"
WORK="${TMPDIR:-/tmp}/siivila-${JOB_ID}"

cleanup() {
  if [[ "${SIIVILA_KEEP_TMPDIR:-0}" == "1" ]]; then
    echo "siivila: SIIVILA_KEEP_TMPDIR=1, keeping job data at $WORK"
  else
    rm -rf "$WORK"
    echo "siivila: deleted job-local data at $WORK"
  fi
}
trap cleanup EXIT

mkdir -p "$WORK/submissions" "$WORK/results"

echo "siivila: cloning $REPO_URL"
git clone --depth 1 "$REPO_URL" "$WORK/repo"

echo "siivila: staging submissions into job-local storage"
cp "$SUBMISSIONS_SRC"/*.pdf "$WORK/submissions/"

cd "$WORK/repo"

# No persistent checkpoints: keep LangGraph state in memory only.
export SIIVILA_DISABLE_CHECKPOINTS=1

srun "$VENV/bin/python" grade.py \
  --backend vllm \
  --model-path "$MODEL_PATH" \
  --input-dir "$WORK/submissions" \
  --output-dir "$WORK/results" \
  --course-config "$COURSE_CONFIG"

echo "siivila: exporting validated results to $RESULTS_DIR"
mkdir -p "$RESULTS_DIR"
find "$WORK/results" -maxdepth 1 -type f \
  \( -name '*.json' -o -name '*.md' -o -name '*.pdf' \) \
  -exec cp {} "$RESULTS_DIR/" \;

echo "siivila: done"
