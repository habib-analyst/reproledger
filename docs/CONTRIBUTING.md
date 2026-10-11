# Contributing to the ledger — publishing recipes & attestations

The ledger is the public log of the reproducibility attestation network.
It lives in this repo under `ledger/` and grows exclusively through pull
requests. No accounts, no servers, no tokens.

## Publishing a recipe (you're an author)

1. Write `recipe.json` following `docs/RECIPE_SPEC.md`.
2. Validate it locally:
   ```
   repro publish recipe.json
   ```
   This prints the recipe hash. If it fails, fix the schema — CI will
   reject invalid recipes anyway.
3. **Run your own recipe first.** `repro verify recipe.json` should PASS
   on your machine. A recipe the author never ran is not a recipe.
4. Open a PR adding exactly one file:
   `ledger/recipes/<recipe-name>/recipe.json`
   (name must match the recipe's `name` field).
5. CI checks: schema validity, commit SHA exists upstream, recipe hash
   matches the filename record. A maintainer merges.

## Attesting a reproduction (you're a verifier)

1. Pick a recipe: `repro log --ledger ledger` (or browse
   `ledger/recipes/` on GitHub).
2. Run it — this is the whole point, one command:
   ```
   repro verify https://raw.githubusercontent.com/habib-analyst/reproledger/main/ledger/recipes/<name>/recipe.json \
     --attest --name "Your Name" --contact "github:yourhandle" --key ~/.ssh/id_ed25519
   ```
   On PASS this mints a signed attestation file. (`--attest` refuses to
   sign non-PASS results — the log records reproductions, not attempts.)
3. Open a PR adding the attestation file under
   `ledger/attestations/<recipe-hash12>/`. CI verifies the SSH signature
   and that the recipe hash matches a published recipe.

You don't need permission. You don't need an account on anything except
GitHub (for the PR). Your key, your hardware, your name in the open log.

## Amending a recipe

Recipes are immutable by hash — to change one, publish a new recipe
(new commit pin, new tolerances) under a new PR. The old recipe and its
attestations stay in the log forever. That's a feature: the history of
what was claimed, and when, is itself data.

## What makes a good recipe

- **Tolerances from measurement, not hope.** Measure your own seed
  spread first; set tolerance >= 2x observed spread.
- **Fast first.** A 2-minute CPU recipe gets verified; a 6-hour GPU
  recipe gets starred and ignored. Publish the fast check even if the
  full run is bigger.
- **`repro pytest tests/ -q`** for test suites — don't hand-roll
  metrics extraction.
- Pin data hashes. "Download latest" is not reproducible.

## Badges

After your recipe has attestations, render its badge:
```
repro badge --ledger ledger --recipe <name> --out badge.svg
```
The badge counts distinct SSH-key fingerprints (independent parties),
with author self-attestations shown separately. Embed it in your README:

```markdown
[![reproduced](https://raw.githubusercontent.com/habib-analyst/reproledger/main/ledger/badges/<name>.svg)](https://github.com/habib-analyst/reproledger/tree/main/ledger/attestations/<hash12>)
```

See `docs/THREAT_MODEL.md` for what the badge does and doesn't prove.
