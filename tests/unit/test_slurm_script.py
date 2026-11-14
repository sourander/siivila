"""Local dry-run of slurm/grade.slurm with stubbed git/uv/sbatch environment.

Roihu access is not required: the script's data-handling behavior (staging
into $TMPDIR, exporting only results, cleanup) is what is verified here.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[2]
SCRIPT = REPO_ROOT / "slurm" / "grade.slurm"

GIT_STUB = """#!/bin/bash
# git clone --depth 1 URL DEST -> just create the destination
for last; do :; done
mkdir -p "$last"
"""

SRUN_STUB = """#!/bin/bash
# srun CMD ... -> run the command directly (single-node dry run)
exec "$@"
"""

PYTHON_STUB = """#!/bin/bash
# venv python grade.py ... --output-dir DIR -> write fake validated results
out=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--output-dir" ]]; then out="$2"; shift 2; else shift; fi
done
echo '{}' > "$out/manifest.json"
echo '# report' > "$out/report.md"
"""


@pytest.fixture
def job_env(tmp_path: Path):
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    for name, body in [("git", GIT_STUB), ("srun", SRUN_STUB)]:
        stub = stub_bin / name
        stub.write_text(body)
        stub.chmod(0o755)

    submissions = tmp_path / "source-pdfs"
    submissions.mkdir()
    (submissions / "student-a.pdf").write_bytes(b"%PDF-1.4 fake\n")
    (submissions / "student-b.pdf").write_bytes(b"%PDF-1.4 fake\n")

    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    python_stub = venv / "bin" / "python"
    python_stub.write_text(PYTHON_STUB)
    python_stub.chmod(0o755)

    tmpdir = tmp_path / "jobtmp"
    tmpdir.mkdir()
    results = tmp_path / "results"

    env = {
        **os.environ,
        "PATH": f"{stub_bin}:{os.environ['PATH']}",
        "TMPDIR": str(tmpdir),
        "SLURM_JOB_ID": "testjob",
        "SIIVILA_VENV": str(venv),
        "SIIVILA_SUBMISSIONS_SRC": str(submissions),
        "SIIVILA_RESULTS_DIR": str(results),
    }
    work = tmpdir / "siivila-testjob"
    return env, work, results, submissions


def _run(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_job_exports_results_and_cleans_tmpdir(job_env):
    env, work, results, _submissions = job_env
    proc = _run(env)
    assert proc.returncode == 0, proc.stderr
    # only validated results are exported
    assert (results / "manifest.json").is_file()
    assert (results / "report.md").is_file()
    # job-local data is gone
    assert not work.exists()
    assert "deleted job-local data" in proc.stdout


def test_keep_tmpdir_debug_mode(job_env):
    env, work, results, _submissions = job_env
    proc = _run({**env, "SIIVILA_KEEP_TMPDIR": "1"})
    assert proc.returncode == 0, proc.stderr
    # submissions were staged into job-local storage, never the repo
    assert (work / "submissions" / "student-a.pdf").is_file()
    assert (work / "repo").is_dir()
    assert "keeping job data" in proc.stdout


def test_missing_results_dir_env_fails(job_env):
    env, _work, _results, _subs = job_env
    env = {k: v for k, v in env.items() if k != "SIIVILA_RESULTS_DIR"}
    proc = _run(env)
    assert proc.returncode != 0
    assert "SIIVILA_RESULTS_DIR" in proc.stderr


def test_script_disables_persistent_checkpoints():
    assert "SIIVILA_DISABLE_CHECKPOINTS=1" in SCRIPT.read_text()


def test_documented_setup_matches_script():
    """README and the script header must document the same Roihu setup."""
    script = SCRIPT.read_text()
    readme = (REPO_ROOT / "README.md").read_text()
    for needle in [
        "/scratch/project_1234/venv-siivila",
        "--system-site-packages",
        "PIP_CACHE_DIR=/scratch/project_1234/pip-cache",
        "module load pytorch",
        "sbatch",
        "srun",
        "grade.py",
    ]:
        assert needle in script, f"{needle!r} missing from script"
        assert needle in readme, f"{needle!r} missing from README"
