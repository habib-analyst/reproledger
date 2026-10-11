"""Recipe schema v1 — the heart of reproledger.

A recipe is an author's machine-checkable claim: "run THIS command on THIS
code at THIS commit with THESE data files, and you will observe THESE
metrics within THESE tolerances." Everything a stranger needs to reproduce
a result, pinned and hashed.
"""

import json
import re
from pathlib import Path

from .canonical import sha256_hex

SCHEMA_VERSION = "1.0"

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
COMPARE_MODES = ("within", "ge", "le", "exact")


class RecipeError(ValueError):
    pass


def _req(obj, key, ctx):
    if key not in obj:
        raise RecipeError(f"{ctx}: missing required field '{key}'")
    return obj[key]


def _check(cond, msg):
    if not cond:
        raise RecipeError(msg)


def validate_metric(name, spec, ctx):
    _check(isinstance(spec, dict), f"{ctx}: metric '{name}' must be an object")
    _req(spec, "expected", f"{ctx}: metric '{name}'")
    _check(isinstance(spec["expected"], (int, float)),
           f"{ctx}: metric '{name}.expected' must be a number")
    tol = spec.get("tolerance", 0)
    _check(isinstance(tol, (int, float)) and tol >= 0,
           f"{ctx}: metric '{name}.tolerance' must be a non-negative number")
    mode = spec.get("compare", "within")
    _check(mode in COMPARE_MODES,
           f"{ctx}: metric '{name}.compare' must be one of {COMPARE_MODES}")
    return {"expected": spec["expected"], "tolerance": tol, "compare": mode}


def validate(recipe):
    """Validate a recipe dict against schema v1. Returns normalized dict."""
    ctx = "recipe"
    _check(isinstance(recipe, dict), "recipe must be a JSON object")
    _check(recipe.get("reproledger") == SCHEMA_VERSION,
           f"recipe.reproledger must be '{SCHEMA_VERSION}'")
    name = _req(recipe, "name", ctx)
    _check(isinstance(name, str) and NAME_RE.match(name),
           "recipe.name must be a lowercase slug (a-z, 0-9, hyphens)")
    _check(isinstance(_req(recipe, "title", ctx), str) and recipe["title"].strip(),
           "recipe.title must be a non-empty string")

    code = _req(recipe, "code", ctx)
    _check(isinstance(code, dict), "recipe.code must be an object")
    repo = _req(code, "repo", ctx + ".code")
    _check(isinstance(repo, str) and repo.startswith(("https://", "git@")),
           "recipe.code.repo must be a git URL")
    commit = _req(code, "commit", ctx + ".code")
    _check(isinstance(commit, str) and SHA_RE.match(commit),
           "recipe.code.commit must be a 40-char git SHA (pinned, no branches)")

    data = recipe.get("data", [])
    _check(isinstance(data, list), "recipe.data must be a list")
    for d in data:
        _check(isinstance(d, dict), "recipe.data entries must be objects")
        _check(isinstance(_req(d, "name", "recipe.data"), str), "data entry needs 'name'")
        h = _req(d, "sha256", "recipe.data")
        _check(isinstance(h, str) and re.match(r"^[0-9a-f]{64}$", h),
               "recipe.data entries need a 64-char sha256")

    env = recipe.get("environment", {})
    _check(isinstance(env, dict), "recipe.environment must be an object")

    _check(isinstance(_req(recipe, "command", ctx), str) and recipe["command"].strip(),
           "recipe.command must be a non-empty string")
    _check(isinstance(_req(recipe, "metrics_file", ctx), str),
           "recipe.metrics_file must be a relative path the command writes")
    _check(not Path(recipe["metrics_file"]).is_absolute(),
           "recipe.metrics_file must be relative, not absolute")

    metrics = _req(recipe, "metrics", ctx)
    _check(isinstance(metrics, dict) and metrics,
           "recipe.metrics must be a non-empty object")
    norm_metrics = {n: validate_metric(n, s, ctx) for n, s in metrics.items()}

    timeout = recipe.get("timeout_s", 3600)
    _check(isinstance(timeout, int) and timeout > 0,
           "recipe.timeout_s must be a positive integer")

    out = {
        "reproledger": SCHEMA_VERSION,
        "name": name,
        "title": recipe["title"],
        "author": recipe.get("author", {}),
        "code": {"repo": repo, "commit": commit,
                 "subdir": code.get("subdir", ".")},
        "data": [{"name": d["name"], "sha256": d["sha256"],
                  "url": d.get("url", ""), "note": d.get("note", "")}
                 for d in data],
        "environment": env,
        "command": recipe["command"],
        "metrics_file": recipe["metrics_file"],
        "metrics": norm_metrics,
        "timeout_s": timeout,
        "hardware": recipe.get("hardware", {}),
        "notes": recipe.get("notes", ""),
    }
    return out


def load(path) -> dict:
    """Load + validate a recipe from a local path or https:// URL."""
    if isinstance(path, str) and path.startswith(("https://", "http://")):
        import tempfile
        import urllib.request
        tmp = Path(tempfile.mkdtemp(prefix="repro-recipe-"))
        dl = tmp / "recipe.json"
        try:
            urllib.request.urlretrieve(path, dl)
        except Exception as e:
            raise RecipeError(f"cannot download recipe {path}: {e}")
        path = dl
    p = Path(path)
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as e:
        raise RecipeError(f"cannot read recipe {path}: {e}")
    return validate(raw)


def recipe_hash(recipe) -> str:
    """Content identity of a recipe: sha256 of its canonical form."""
    return sha256_hex(validate(recipe))


def dump(recipe, path):
    Path(path).write_text(json.dumps(validate(recipe), indent=2) + "\n")
