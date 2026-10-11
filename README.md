# reproledger

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-32%2F32-green.svg)](tests/)
[![reproledger](https://img.shields.io/badge/reproducibility-attested-brightgreen.svg)](ledger/)

**SLSA proves who built it. Nothing proves anyone else can rebuild it — until now.**

reproledger is the reproducibility attestation network: authors publish
machine-checkable *repro recipes* (code commit + data hashes + environment
+ command + metric tolerances); anyone re-runs a recipe with one command;
passing runs become *signed attestations* in a public append-only log.
Models and benchmarks earn **"reproduced by N independent parties"**
badges — a web of trust for weights.

The public log is just a GitHub repo (`ledger/` in this repo). No
blockchain, no servers, no tokens. Append = pull request. $0 forever.

## Quickstart

```bash
pip install reproledger

# 1. Verify someone's result in one command
repro verify https://raw.githubusercontent.com/habib-analyst/reproledger/main/ledger/recipes/benchshield-tests/recipe.json

# 2. On PASS, mint a signed attestation and PR it into the log
repro verify <recipe> --attest --name "Your Name" --contact "github:you" --key ~/.ssh/id_ed25519

# 3. Query the network
repro log --ledger ledger
repro badge --ledger ledger --recipe benchshield-tests --out badge.svg
```

Expected output for step 1:

```
recipe:  benchshield-tests  (931fb81c2ee5…)
verdict: PASS
  [ok] tests_passed: observed=13 expected=13 ±0 (ge) — 13 >= 13 - 0
  [ok] tests_failed: observed=0 expected=0 ±0 (le) — 0 <= 0 + 0
elapsed: 121.4s
```

## Measured results

The network launches with 14 seed recipes for real projects (all
`habib-analyst` repos, commits pinned). Dogfood status:

| recipe | claim | verification |
|---|---|---|
| benchshield-tests | 13/13 tests pass | **PASS, author-verified 2026-10-11** (13 passed in 114s, fresh clone + venv) |
| agent-autopsy-tests | 16/16 tests pass | published, awaiting independent verification |
| agent-heal-tests | 35/35 tests pass | published, awaiting independent verification |
| mcp-autopsy-tests | 7/7 tests pass | published, awaiting independent verification |
| conformal-med-tests | 10/10 tests pass | published, awaiting independent verification |
| medjax-tests | 40/40 tests pass | published, awaiting independent verification |
| robocorrupt-bench-tests | 6/6 tests pass | published, awaiting independent verification |
| innkeeper-tests | 21/21 tests pass | published, awaiting independent verification |
| agent-scientist-medmnist-tests | 11/11 tests pass | published, awaiting independent verification |
| synsync-bench-tests | 6/6 tests pass | published, awaiting independent verification |
| forge-tests | 14/14 tests pass | published, awaiting independent verification |
| vertebrae-cleanup-tests | 8/8 tests pass | published, awaiting independent verification |
| fedsec-sim-tests | 32/32 tests pass | published, awaiting independent verification |
| coflight-tests | 75/75 tests pass | published, awaiting independent verification |

CLI test suite: **32/32 green**. Signature round-trips, tamper rejection,
ledger party-counting, and badge rendering all covered.

## How it works

```
author                          verifier                         ledger (this repo)
  │                                 │                                   │
  │  repro publish recipe.json      │                                   │
  │  (validates schema, hashes)     │                                   │
  │ ── PR: ledger/recipes/<name>/ ──▶│                                  │
  │                                 │  repro verify <recipe-url>        │
  │                                 │  1. clone @ pinned commit        │
  │                                 │  2. check out, verify HEAD       │
  │                                 │  3. fresh venv + setup           │
  │                                 │  4. run command, read metrics     │
  │                                 │  5. compare vs tolerances        │
  │                                 │  ── PR: ledger/attestations/ ───▶│
  │                                 │     (SSH-signed attestation)      │
```

**Recipe** = the author's machine-checkable claim: code repo + pinned
commit + data SHA-256s + env setup + command + expected metrics with
tolerances and compare modes (`within`/`ge`/`le`/`exact`). Full spec:
`docs/RECIPE_SPEC.md`.

**Attestation** = the verifier's signed statement binding recipe hash,
observed metrics, hardware fingerprint, timestamp, and identity —
signed with their SSH key (`ssh-keygen -Y`, the same primitive as signed
commits). `repro check` verifies any attestation offline.

**Counting rule** (the anti-gaming core): an *independent party* is a
distinct SSH-key fingerprint — ten attestations from one key count as
one. The recipe author's own runs are labeled `self_attested` and shown
separately on the badge. Everything (timestamps, hardware, pubkeys,
metrics) is public, so fakery is a signed lie attached to your name —
the social cost is the deterrent. Full honest limits:
`docs/THREAT_MODEL.md`.

## Why this exists

My [benchshield](https://github.com/habib-analyst/benchshield) project
*detects* unreliable benchmarks — cherry-picked seeds, train/test
contamination, scaffold sensitivity. But detection without incentives
changes nothing: authors still get cited for unreproducible numbers
because there's no reward for being reproducible.

reproledger fixes the incentive. A badge that says *"reproduced by 7
independent parties"* is a citable, visible asset — journals, hiring
committees, and users can see it. Reproducibility becomes something you
*earn* and *show*, not something reviewers beg for.

Related work, honestly placed: [reprocheck](https://github.com/habib-analyst/reprocheck)
(my own) audits whether a *paper's text* reports reproducibility signals —
reproledger *executes* the reproduction. SLSA/Sigstore prove *provenance*
(who built an artifact); reproledger proves *reproducibility* (anyone
else can rebuild it). Code Ocean hosts reproductions behind a paywall;
this network is a GitHub repo.

## Contributing

Publish a recipe or attest a reproduction — no permission needed:
`docs/CONTRIBUTING.md`. The ledger grows through PRs.

## Citation

```bibtex
@software{rehman2026reproledger,
  author  = {Habib Ur Rehman},
  title   = {reproledger: The Reproducibility Attestation Network},
  year    = {2026},
  url     = {https://github.com/habib-analyst/reproledger}
}
```

---
Built by [Habib Ur Rehman](https://github.com/habib-analyst) · ML/AI Engineer & healthcare-AI researcher ·
[LinkedIn](https://www.linkedin.com/in/hur-dev) · [habib.top](https://habib.top)
