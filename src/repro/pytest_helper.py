"""`repro pytest` — the one-command metrics writer for test-suite recipes.

Runs pytest and writes a metrics JSON file the recipe's metrics_file
points at. This is what makes "verify a stranger's test suite in one
command" real: the recipe command is just `repro pytest tests/ -q`.

Interpreter choice matters: `repro verify` may run the recipe command
inside a FRESH venv (see runner). The helper must use THAT interpreter,
not the one running the `repro` CLI — so it prefers $VIRTUAL_ENV/bin/python,
then PATH-resolved python3.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SUMMARY_RE = re.compile(
    r"(?P<failed>\d+) failed|(?P<passed>\d+) passed|(?P<skipped>\d+) skipped|"
    r"(?P<errors>\d+) error", re.IGNORECASE)


def _target_python():
    ve = os.environ.get("VIRTUAL_ENV")
    if ve:
        p = Path(ve) / "bin" / "python"
        if p.exists():
            return str(p)
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            return found
    return sys.executable


def run_pytest(args, metrics_file):
    cmd = [_target_python(), "-m", "pytest"] + args
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True)
    out = p.stdout
    counts = {"failed": 0, "passed": 0, "skipped": 0, "errors": 0}
    # parse the LAST summary line ("3 failed, 12 passed in 4.2s")
    for line in reversed(out.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            for m in SUMMARY_RE.finditer(line):
                for k in counts:
                    if m.group(k):
                        counts[k] = max(counts[k], int(m.group(k)))
            break
    metrics = {"tests_passed": counts["passed"],
               "tests_failed": counts["failed"],
               "tests_skipped": counts["skipped"],
               "tests_errors": counts["errors"],
               "pytest_rc": p.returncode}
    Path(metrics_file).write_text(json.dumps(metrics, indent=2) + "\n")
    sys.stdout.write(out)
    return p.returncode
