# The ledger — the public log of the reproducibility attestation network

This directory IS the network. No blockchain, no database, no server:
recipes and signed attestations as files, appended via pull request,
validated by CI.

```
ledger/
  recipes/<name>/recipe.json                 # published repro recipes
  attestations/<recipe-hash12>/<ts>-<who>.json  # signed attestations
  badges/<name>.svg                          # rendered badges
```

## Reading it

```
repro log --ledger ledger                    # every recipe, who reproduced it
repro log --ledger ledger --recipe benchshield-tests
repro badge --ledger ledger --recipe benchshield-tests --out badge.svg
```

## Trust rules (enforced socially, documented in docs/THREAT_MODEL.md)

- An **independent party** = a distinct SSH-key fingerprint. Ten
  attestations from one key = one party.
- **`self_attested: true`** = the recipe author's own run. Counted
  separately on the badge, never in the independence number.
- Every attestation is public: timestamp, hardware, pubkey, observed
  metrics. Fake attestations are signed lies attached to your name,
  in public, permanently.

## Seed recipes

The network launches with recipes for Habib Ur Rehman's own projects —
the dogfood that proves the system works on real code:

| recipe | what it reproduces | status |
|---|---|---|
| benchshield-tests | 13/13 integrity probes | author-verified 2026-10-11 |
| agent-autopsy-tests | 16/16 autopsy tests | published |
| agent-heal-tests | 35/35 healer tests | published |
| mcp-autopsy-tests | 7/7 MCP tests | published |
| conformal-med-tests | 10/10 conformal tests | published |
| medjax-tests | 40/40 parity tests | published |
| robocorrupt-bench-tests | 6/6 benchmark tests | published |
| innkeeper-tests | 21/21 sim tests | published |
| agent-scientist-medmnist-tests | 11/11 loop tests | published |
| synsync-bench-tests | determinism + pipeline | published |
| forge-tests | forge suite | published |
| vertebrae-cleanup-tests | cleanup suite | published |
| fedsec-sim-tests | CAC defense suite | published |
| coflight-tests | routing + economics | published |
