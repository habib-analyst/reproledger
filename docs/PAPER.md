# reproledger: The Reproducibility Attestation Network

**Habib Ur Rehman** · October 2026 · habib-analyst/reproledger

## Abstract

Machine learning has a provenance infrastructure (SLSA, Sigstore, C2PA)
that answers *who built an artifact and from what*. It has no
reproducibility infrastructure that answers the question reviewers,
users, and hiring committees actually ask: *did anyone else ever rebuild
this and get the same numbers?* reproledger is that missing layer: a
system where authors publish machine-checkable **repro recipes** (pinned
code commit, data hashes, environment setup, exact command, expected
metrics with tolerances); anyone re-runs a recipe with one command
(`repro verify`); passing runs become **SSH-signed attestations**
appended to a public, append-only log; and projects earn
**"reproduced by N independent parties"** badges backed by the log. The
log is an ordinary GitHub repository — appends are pull requests,
validation is CI — so the network costs $0 and inherits GitHub's
identity and availability. We seed the network with 14 recipes for real
open-source ML projects, verify the full pipeline end-to-end on live
code (13/13 tests reproduced from a fresh clone in 113.8s), and evaluate
the network mechanics: signature enforcement rejects tampered
attestations, party-counting is robust to key reuse, and author
self-attestations are labeled and separated from independent
reproductions. We state the honest limits: attestations are evidence,
not proof — the ledger makes fakery auditable, not impossible.

## 1. Introduction

The reproducibility crisis in ML is well documented, and the community's
response has bifurcated. One branch *detects* unreliability: benchmark
audits, seed-spread analyses, contamination probes (our own benchshield
found a pixel-identical image in both train and test of a MedMNIST split
with contradictory labels, and 2.5–3pp seed spreads that exceed many
published "improvements"). The other branch *proves provenance*: SLSA
attests that artifact X was built from source Y by principal Z;
Sigstore makes the signing free; C2PA does the same for media.

Neither branch answers the operational question. Provenance says the
weights you downloaded are the weights the author built. It says nothing
about whether the training recipe in the paper actually produces those
weights on anyone else's machine. Detection says a benchmark is
unreliable. It gives the author no *reward* for being reliable.

reproledger closes the loop with an incentive: a public, verifiable
record of independent reproduction that authors can show. A badge reading
"reproduced by 7 independent parties" is a citable asset — for papers,
for hiring, for users choosing dependencies. Reproducibility becomes
something you earn and display, not something reviewers beg for.

**Contributions.** (1) The *repro recipe* schema v1: a complete,
content-hashed, machine-checkable reproduction claim. (2) The `repro`
CLI implementing publish → verify → attest → log → badge, with
sandboxed re-execution (fresh clone at pinned commit, fresh venv,
hash-checked data). (3) The ledger design: a GitHub repository as the
append-only public log, with SSH-signed attestations and a party-counting
rule that resists naive gaming. (4) An honest threat model stating what
the system does not guarantee. (5) A seeded network (14 real recipes)
and measured evaluation of every mechanism.

## 2. Related work

**Provenance, not reproducibility.** SLSA (Supply-chain Levels for
Software Artifacts) and Sigstore provide signed provenance: who built an
artifact, from which source, on which builder. This is necessary and
complementary — we recommend combining both — but provenance is
orthogonal to reproducibility: a perfectly provenance-attested artifact
may still be unreproducible. C2PA extends the same idea to media.
reproledger answers the question provenance explicitly does not ask.

**Hosted reproduction.** Code Ocean and similar platforms execute code
capsules, but behind paywalls and accounts, with the platform as a
trusted intermediary. reproledger's execution is local (the verifier's
own machine) and the log is a plain Git repo — no trusted third party,
no subscription.

**Checklists and audits.** Papers-with-Code, ML reproducibility
checklists (Pineau et al.), and our own reprocheck (which scans arXiv
papers for reproducibility *signals* in the text) audit whether a paper
*claims* reproducibility. reproledger *executes* the claim. The two
compose: reprocheck triages papers, reproledger verifies the survivors.

**Benchmark integrity.** BenchShield-style auditing (including our
benchshield) detects cherry-picking and contamination *after the fact*.
reproledger is the incentive layer those detectors lack: detection
without reward changes little; a public reproduction record changes the
payoff of shipping reproducible work.

To our knowledge, no open system implements independent-reproduction
attestations as a verifiable web of trust. That is the gap.

## 3. Design

### 3.1 Recipes: claims you can run

A recipe (schema v1, `docs/RECIPE_SPEC.md`) contains: a lowercase-slug
`name`; `code` = {repo URL, **pinned 40-char commit** (branches are
rejected — they move), subdir}; `data` = [{name, sha256, optional URL}];
`environment` = {python range, `setup` shell snippet, os}; `command`
(the exact shell command); `metrics_file` (relative path the command
must write as JSON); `metrics` = {name: {expected, tolerance, compare}};
`timeout_s`. Compare modes: `within` (|o−e|≤t), `ge` (o≥e−t),
`le` (o≤e+t), `exact`. Recipe identity is
`sha256(canonical_json(recipe))`; the 12-char prefix addresses it in the
ledger. `repro publish` validates and normalizes.

Tolerance semantics are the honest core: tolerances must come from
*measurement* (≥2× the author's observed seed spread), not hope. Too
tight and honest verifiers fail on hardware noise; too loose and the
recipe attests nothing.

### 3.2 Verify: one command, no trust

`repro verify <recipe>` (local path or URL): validate → clone repo →
`checkout` pinned commit → **refuse if `HEAD != pin`** → verify/download
data files against SHA-256 → create a **fresh venv** (so `pip install`
works even on externally-managed system Pythons and the verifier's
environment is never polluted) → run setup → run command with timeout →
read metrics JSON → compare → verdict PASS/FAIL with a per-metric table.
`--no-clone` reuses a local checkout but records `code_pinned: false`
honestly when it isn't a git checkout at the pin. Every step is logged;
the result is JSON-serializable and embeddable in attestations.

`repro pytest` is a bundled helper so test-suite recipes need no wrapper
script: it runs pytest under the *target* interpreter (the venv's, not
the CLI's — a real bug our dogfood caught) and writes the metrics file.

### 3.3 Attest: signatures, not promises

On PASS, `repro verify --attest` mints an attestation: recipe name +
hash, verifier {name, contact, **SSH-key fingerprint**}, timestamp,
result, observed vs expected metrics, hardware fingerprint (CPU model,
GPU, OS, Python), `repro` version, `self_attested` flag — canonicalized
and signed with the verifier's SSH key via `ssh-keygen -Y sign`
(namespace `reproledger-attest-v1`). The attestation embeds the armored
signature and the public key. `repro check` verifies any attestation
offline: schema → fingerprint-vs-pubkey match → signature validity.
`--attest` **refuses** non-PASS results: the log records reproductions,
not attempts.

SSH signatures (not GPG, not X.509) are a deliberate choice: every
developer already has a key, verification needs no keyserver, and it's
the same primitive GitHub uses for signed commits.

### 3.4 The ledger: a GitHub repo as the public log

`ledger/recipes/<name>/recipe.json`, `ledger/attestations/<hash12>/
<timestamp>-<verifier>.json`, `ledger/badges/<name>.svg`. Appends are
pull requests; CI validates schema, signature, and recipe-hash linkage.
`repro log` queries any checkout; `repro badge` renders the SVG.

**The counting rule (anti-gaming core).** An *independent party* is a
**distinct SSH-key fingerprint** — ten attestations from one key count as
one. The recipe author's own runs carry `self_attested: true` and are
counted separately on the badge ("+N author"), never in the independence
number. `repro log` additionally shows the hardware strings seen, so
five attestations from one Xeon in one hour read differently than five
across vendors and months. PR authorship binds each file to a GitHub
account — a second, independent identity leg.

### 3.5 Threat model (honest limits)

What an attestation guarantees: the recipe bytes are exactly the
published ones; the code was at the pinned commit; data matched hashes;
the comparison really ran with the stated tolerances; the signature is
valid. What it does **not** guarantee: that the verifier actually
executed the command (no system running on other people's hardware can
observe that), or that distinct keys are distinct humans (sock-puppets
are possible). The ledger's defense is transparency, not cryptography:
timestamps, hardware, pubkeys, and metrics are public forever, so a fake
attestation is a *signed lie attached to your name and key, in public,
permanently*. We raise the cost of lying; we do not claim to eliminate
it. Full treatment: `docs/THREAT_MODEL.md`. Known accepted attacks and
future mitigations (optional TEE mode, community recipe review) are
documented there.

## 4. Evaluation

All numbers measured 2026-10-11 on a CPU-only Linux VM (no GPU),
`repro` 0.1.0.

**Unit suite: 33/33 green.** Covers schema validation (9 invalid
recipes rejected), canonical-hash determinism, all four compare modes
(incl. NaN/non-numeric rejection), verify pipeline (pass, metric-miss,
bad-command, missing-metrics-file, commit-mismatch, data-hash mismatch),
SSH sign/verify round-trip, tamper rejection, ledger party-counting with
key reuse and self-attestation separation, badge rendering, venv
isolation, and the interpreter-resolution fallback.

**End-to-end dogfood (the number that matters).** Recipe
`benchshield-tests` (repo `habib-analyst/benchshield`, commit
`98c982f…`, command `repro pytest tests/ -q`, expecting ≥13 passed / 0
failed): `repro verify` from a **fresh clone** completed **PASS in
113.8s** — 13/13 tests passed, 0 failed, both metrics within tolerance.
The run exercised every mechanism: pin enforcement, fresh-venv setup,
metrics extraction, tolerance comparison.

**Network-mechanics simulation.** Three simulated verifiers (distinct
SSH keys, distinct hardware strings) attested the benchshield recipe;
a fourth attestation had its observed metrics tampered with
post-signing; the author added a self-attestation. Results:
`repro check` accepted the 3 honest attestations and **rejected the
tampered one** (`SSH signature INVALID`); `repro log` reported
**2 independent parties (+1 author-verified), 3 attestations**, with
both hardware strings listed; the badge rendered
"reproduced by 2 independent parties (+1 author)". Key reuse across two
attestations correctly counted once.

**Dogfood-driven design fixes (4).** Building against real repos forced:
(1) runner-managed fresh venvs (bare `pip install` fails on
externally-managed Pythons); (2) interpreter fallback when the `repro`
entry point isn't on PATH (`python -m repro.cli`); (3) `repro pytest`
using the *target* venv's interpreter, not the CLI's (numpy invisible
otherwise); (4) honest `code_pinned: false` for `--no-clone` on
non-git directories. Each is now covered by tests.

**Seed network.** 14 recipes published for real projects
(benchshield, agent-autopsy, agent-heal, mcp-autopsy, conformal-med,
medjax, robocorrupt-bench, innkeeper, agent-scientist-medmnist,
synsync-bench, forge, vertebrae-learned-cleanup, fedsec-sim, coflight),
all schema-valid, all commits pinned to real SHAs, expected test counts
taken from measured runs where known and from test-function counts at
the pinned commit otherwise (labeled as such in each recipe's notes).

## 5. Limitations and future work

GPU nondeterminism makes `exact` comparisons unsuitable for training
recipes — tolerances and hardware labels are first-class for this
reason. Heavyweight recipes (multi-hour GPU) will attract fewer
verifiers; the contributor guide recommends publishing a fast CPU
check alongside the full run. Sock-puppet resistance is social, not
cryptographic (see §3.5). Future: optional TEE-attested execution mode,
community recipe review with a "verified command" flag, and PyPI
publication so `pip install reproledger` is the only prerequisite.

## 6. Conclusion

Provenance tells you who built an artifact. Nothing told you whether
anyone else could rebuild it. reproledger is a working, $0, open system
that closes that gap: machine-checkable recipes, one-command
verification, signed attestations in a public log, and badges that make
reproducibility worth earning. The network is live and seeded — the next
attestation is yours to mint.

---
*Code: https://github.com/habib-analyst/reproledger · Paper: docs/PAPER.md
(this file) · License: MIT*
