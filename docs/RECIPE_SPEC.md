# Recipe spec v1

A **recipe** is an author's machine-checkable claim:

> run THIS command on THIS code at THIS commit with THESE data files,
> and you will observe THESE metrics within THESE tolerances.

Everything a stranger needs to reproduce a result, pinned and hashed.
If any link in the chain isn't pinned, the recipe doesn't validate.

## Schema

```json
{
  "reproledger": "1.0",
  "name": "benchshield-tests",
  "title": "benchshield test suite (13 tests)",
  "author": {"name": "Habib Ur Rehman",
             "url": "https://github.com/habib-analyst"},
  "code": {
    "repo": "https://github.com/habib-analyst/benchshield",
    "commit": "98c982f55edde9052f8f028a9d0b4c7fbb7986f6",
    "subdir": "."
  },
  "data": [],
  "environment": {
    "python": ">=3.10",
    "setup": "python3 -m pip install --user -e . pytest",
    "os": "linux-x86_64",
    "cpu_only": true
  },
  "command": "repro pytest tests/ -q",
  "metrics_file": "repro_metrics.json",
  "metrics": {
    "tests_passed": {"expected": 13, "tolerance": 0, "compare": "ge"},
    "tests_failed": {"expected": 0, "tolerance": 0, "compare": "le"}
  },
  "timeout_s": 900,
  "hardware": {"gpu_required": false},
  "notes": "Full 13-test suite incl. cherry-pick and contamination probes."
}
```

### Field rules

| field | rule |
|---|---|
| `reproledger` | must be `"1.0"` (schema version) |
| `name` | lowercase slug `[a-z0-9-]` — the recipe's identity in the ledger |
| `code.commit` | **40-char SHA, never a branch.** Branches move; reproductions must not. |
| `data[].sha256` | 64-char SHA-256 of the exact bytes. If the file is missing locally and `url` is set, `repro verify` downloads it and refuses on hash mismatch. |
| `command` | shell command run in the code checkout. Must write `metrics_file`. |
| `metrics_file` | relative path (never absolute) the command writes as a JSON object. |
| `metrics` | each entry: `expected` (number), `tolerance` (>= 0), `compare` mode. |
| `timeout_s` | positive integer; the run is killed past it (verdict FAIL). |

### Compare modes

- `within`: `|observed - expected| <= tolerance` (default)
- `ge`: `observed >= expected - tolerance` — "at least this good"
- `le`: `observed <= expected + tolerance` — "at most this bad"
- `exact`: `observed == expected` — bit-for-bit claims (use sparingly; GPU nondeterminism is real)

**Tolerance guidance.** Tolerances are the honest part of a recipe. Too
tight and every honest verifier FAILs on hardware noise; too loose and the
recipe attests nothing. For stochastic training: measure your own
seed spread first (benchshield exists for exactly this) and set tolerance
>= 2x your observed spread. For deterministic test suites: `ge` with
tolerance 0.

### Setup convention

`environment.setup` runs on the verifier's machine before your command.
Write it defensively — many systems (Debian, this VM) have
externally-managed Pythons where bare `pip install` refuses. You don't need to worry about it: when `setup` is present,
`repro verify` creates a FRESH venv (`<workdir>/venv`), runs your setup
inside it, then runs your command with the venv on PATH. So plain
`pip install` is safe — even on externally-managed system Pythons —
and the verifier's own environment is never polluted. The `repro` CLI
itself stays visible (venv bin is *prepended* to PATH, not replacing it),
so `repro pytest` works as a recipe command.

```
"setup": "pip install -q -e . pytest"
```

The verifier is expected to have the `repro` CLI installed
(`pip install reproledger`) — document that prerequisite in `notes`.
Omit `setup` entirely if your command needs no installation.

### Recipe identity

`sha256(canonical_json(recipe))` — the 12-char prefix addresses the
recipe in `ledger/attestations/`. Two recipes with the same bytes are the
same recipe on every machine, no registry needed.

## The `repro pytest` helper

Test-suite recipes shouldn't need a wrapper script. `repro pytest` runs
pytest and writes the metrics file for you:

```
command: "repro pytest tests/ -q"
metrics_file: "repro_metrics.json"   # written by the helper
metrics: {"tests_passed": {...}, "tests_failed": {...}, ...}
```

Metrics written: `tests_passed`, `tests_failed`, `tests_skipped`,
`tests_errors`, `pytest_rc`.

## Publishing

1. `repro publish recipe.json` — validates and prints the recipe hash.
2. Open a PR against the ledger repo adding
   `ledger/recipes/<name>/recipe.json`.
3. CI checks schema validity (and that the commit exists upstream).

See CONTRIBUTING.md for the full flow.
