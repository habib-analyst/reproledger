"""The verify pipeline: the one-command reproduction.

  repro verify --recipe recipe.json [--workdir DIR] [--no-clone] [--attest]

Steps:
  1. load + validate recipe
  2. prepare workspace (default: fresh temp dir): git clone --quiet the repo,
     checkout the PINNED commit, refuse if HEAD != pinned commit
  3. verify data file hashes (download if a URL is given and file missing)
  4. optional environment setup (recipe.environment.setup shell snippet)
  5. run recipe.command with recipe.timeout_s, capture logs
  6. read recipe.metrics_file (JSON), compare against tolerances
  7. verdict PASS/FAIL + per-metric table; optionally build an attestation

Nothing here is magic — the point is that every step is explicit, logged,
and content-pinned, so a stranger's PASS means the same thing as yours.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .canonical import sha256_file_hex
from .metrics import compare_all
from .recipe import RecipeError, load as load_recipe, recipe_hash

REPRO_VERSION = "0.1.0"


class VerifyError(RuntimeError):
    pass


def _run(cmd, cwd, timeout, env=None):
    """Run a shell command, capturing output. Returns (rc, stdout, stderr, elapsed)."""
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           env=env, text=True)
        return p.returncode, p.stdout, p.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace") if e.stdout else ""
        err = (e.stderr or b"").decode("utf-8", "replace") if e.stderr else ""
        return 124, out, err, time.time() - t0


def _git(cmd, cwd):
    p = subprocess.run(["git"] + cmd, cwd=cwd, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    if p.returncode != 0:
        raise VerifyError(f"git {' '.join(cmd)} failed: {p.stderr.strip()[:300]}")
    return p.stdout.strip()


def prepare_code(recipe, workdir, no_clone=False):
    """Clone the repo at the pinned commit into workdir/code.

    Returns (rundir, pinned: bool). With --no-clone on a non-git dir the
    code identity is NOT pinned — recorded honestly in the result.
    """
    code = recipe["code"]
    dest = Path(workdir) / "code"
    if no_clone:
        if not dest.exists():
            raise VerifyError(f"--no-clone but {dest} does not exist")
        # best effort: if it's a git checkout, enforce the pinned commit
        p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=dest,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True)
        if p.returncode == 0:
            head = p.stdout.strip()
            if head != code["commit"]:
                raise VerifyError(
                    f"--no-clone dir is at {head}, recipe pins "
                    f"{code['commit']} — refusing to verify the wrong code")
            pinned = True
        else:
            pinned = False  # not a git checkout; code identity unpinned
    else:
        if shutil.which("git") is None:
            raise VerifyError("git is required to fetch recipe code")
        if dest.exists():
            shutil.rmtree(dest)
        rc, out, err, _ = _run(f"git clone --quiet {code['repo']} {dest}",
                               cwd=workdir, timeout=600)
        if rc != 0:
            raise VerifyError(f"git clone failed: {err.strip()[:300]}")
        _git(["checkout", "--quiet", code["commit"]], cwd=dest)
        head = _git(["rev-parse", "HEAD"], cwd=dest)
        if head != code["commit"]:
            raise VerifyError(
                f"code commit mismatch: recipe pins {code['commit']}, "
                f"checkout is {head} — refusing to verify the wrong code")
        pinned = True
    subdir = Path(dest) / code.get("subdir", ".")
    if not subdir.is_dir():
        raise VerifyError(f"code subdir {code.get('subdir', '.')} not found")
    return subdir, pinned


def prepare_data(recipe, workdir):
    """Verify (and if needed, download) pinned data files."""
    data_dir = Path(workdir) / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for d in recipe.get("data", []):
        target = data_dir / d["name"]
        if target.exists():
            got = sha256_file_hex(target)
            if got != d["sha256"]:
                raise VerifyError(
                    f"data file {d['name']}: sha256 mismatch "
                    f"(expected {d['sha256'][:12]}…, got {got[:12]}…)")
        elif d.get("url"):
            try:
                urllib.request.urlretrieve(d["url"], target)
            except Exception as e:
                raise VerifyError(f"data download failed for {d['name']}: {e}")
            got = sha256_file_hex(target)
            if got != d["sha256"]:
                target.unlink(missing_ok=True)
                raise VerifyError(f"downloaded {d['name']} failed hash check")
        else:
            raise VerifyError(
                f"data file {d['name']} missing and no URL to fetch it")
    return data_dir


def run_command(recipe, rundir, workdir):
    """Run the recipe command. Returns dict with rc/stdout/stderr/elapsed.

    If the recipe declares environment.setup, it runs inside a FRESH venv
    created at <workdir>/venv (PATH prepended, VIRTUAL_ENV set) — so
    `pip install` in setup just works, even on externally-managed system
    Pythons, and the verifier's own environment is never polluted.
    Without setup, the command runs in the verifier's current environment.
    """
    env = recipe.get("environment", {})
    run_env = dict(os.environ)
    used_venv = False
    if env.get("setup"):
        venv = Path(workdir) / "venv"
        rc, out, err, _ = _run(f"python3 -m venv {venv}", cwd=workdir,
                               timeout=300)
        if rc != 0:
            raise VerifyError(f"could not create venv: {err.strip()[:300]}")
        run_env["VIRTUAL_ENV"] = str(venv)
        run_env["PATH"] = f"{venv}/bin:{run_env.get('PATH', '')}"
        used_venv = True
        rc, out, err, _ = _run(env["setup"], cwd=rundir,
                               timeout=recipe["timeout_s"], env=run_env)
        if rc != 0:
            raise VerifyError(f"environment setup failed (rc={rc}): "
                              f"{err.strip()[:500]}")
    rc, out, err, elapsed = _run(_resolve_repro(recipe["command"], run_env),
                              cwd=rundir, timeout=recipe["timeout_s"],
                              env=run_env)
    return {"rc": rc, "stdout": out, "stderr": err,
            "elapsed_s": round(elapsed, 2), "used_venv": used_venv}


def _resolve_repro(command, env):
    """If the `repro` entry point isn't on PATH (dev checkouts, `python -m`
    invocations), serve the helper through this same interpreter instead of
    failing. The verifier is definitionally running repro already."""
    import shutil as _shutil
    if _shutil.which("repro", path=env.get("PATH")) is not None:
        return command
    if command == "repro":
        return f'"{sys.executable}" -m repro.cli'
    if command.startswith("repro "):
        return f'"{sys.executable}" -m repro.cli ' + command[len("repro "):]
    return command


def read_metrics(recipe, rundir):
    mf = Path(rundir) / recipe["metrics_file"]
    if not mf.exists():
        raise VerifyError(
            f"command finished but metrics file '{recipe['metrics_file']}' "
            f"was not written")
    try:
        obj = json.loads(mf.read_text())
    except json.JSONDecodeError as e:
        raise VerifyError(f"metrics file is not valid JSON: {e}")
    if not isinstance(obj, dict):
        raise VerifyError("metrics file must contain a JSON object")
    return obj


def observe_environment():
    """Best-effort hardware/software fingerprint for the attestation."""
    cpu = platform.processor() or platform.machine()
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    gpu = "none"
    if shutil.which("nvidia-smi"):
        try:
            p = subprocess.run(["nvidia-smi", "--query-gpu=name",
                                "--format=csv,noheader"],
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, timeout=10)
            names = [l.strip() for l in p.stdout.splitlines() if l.strip()]
            if names:
                gpu = "; ".join(names)
        except Exception:
            pass
    return {"os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "cpu": cpu, "gpu": gpu,
            "python": platform.python_version()}


def verify(recipe_path, workdir=None, no_clone=False, keep=False):
    """Full verify pipeline. Returns a result dict (JSON-serializable)."""
    recipe = load_recipe(recipe_path)  # handles local paths and https:// URLs
    rhash = recipe_hash(recipe)
    tmp = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="repro-"))
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    result = {
        "reproledger": "1.0",
        "kind": "verify_result",
        "recipe_name": recipe["name"],
        "recipe_hash": rhash,
        "repro_version": REPRO_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "code_pinned": None,
        "environment_observed": observe_environment(),
    }
    try:
        rundir, pinned = prepare_code(recipe, tmp, no_clone=no_clone)
        result["code_pinned"] = pinned
        prepare_data(recipe, tmp)
        run = run_command(recipe, rundir, tmp)
        result["command"] = {"cmd": recipe["command"], **run,
                             "log_tail": run["stdout"][-2000:]}
        if run["rc"] != 0:
            result["verdict"] = "FAIL"
            result["failure"] = (f"command exited rc={run['rc']}: "
                                 f"{run['stderr'][-500:].strip()}")
            return result
        observed = read_metrics(recipe, rundir)
        verdict, rows = compare_all(observed, recipe)
        result["verdict"] = verdict
        result["metrics_observed"] = observed
        result["metrics_expected"] = {
            n: {"expected": s["expected"], "tolerance": s["tolerance"],
                "compare": s["compare"]}
            for n, s in recipe["metrics"].items()}
        result["metric_rows"] = rows
        return result
    except VerifyError as e:
        result["verdict"] = "FAIL"
        result["failure"] = str(e)
        return result
    finally:
        result["elapsed_s"] = round(time.time() - t0, 2)
        if not keep and workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)
