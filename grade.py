#!/usr/bin/env python3
"""Direct-invocation entry point for Roihu batch jobs.

Roihu does not use uv; the Slurm job runs this file with the scratch venv's
interpreter: srun "$VENV/bin/python" grade.py --args
Locally, prefer: uv run grade --args (same CLI, same behavior).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from siivila.cli import main

if __name__ == "__main__":
    sys.exit(main())
