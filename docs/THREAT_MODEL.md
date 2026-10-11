# Threat model — what reproledger does and does NOT guarantee

Honest systems state their limits up front. This is ours.

## What an attestation means

An attestation is a signed statement: "on `<timestamp>`, key `<fingerprint>`
ran recipe `<hash>` and observed metrics within tolerance on hardware
`<cpu/gpu>`." It is **evidence**, not proof. Specifically:

**Guaranteed by construction:**
- The recipe bytes the verifier ran are exactly the published ones
  (content hash; any edit changes the hash and breaks the link).
- The code checkout was at the pinned commit (`git rev-parse HEAD`
  checked post-checkout; mismatch = FAIL, no attestation minted).
- Data files matched their pinned SHA-256 (or the run refused).
- The metrics comparison really happened with the stated tolerances
  (the verify result is embedded in the attestation).
- The signature is valid for the embedded SSH public key, and the
  fingerprint in the verifier record matches that key.

**NOT guaranteed:**
- That the verifier actually ran the command (vs. hand-crafting a
  metrics file). We cannot observe their machine — no system that
  runs on other people's hardware can.
- That two attestations from different keys are different humans.
  Sock-puppets are possible. The ledger makes fakery *auditable*,
  not impossible.

## Anti-gaming design (raising the cost of lying)

1. **Parties, not attestations.** The badge counts distinct SSH-key
   fingerprints, never raw attestation counts. Ten attestations from
   one key = one party.
2. **Self-attestations are labeled.** The recipe author's own runs are
   marked `self_attested: true` and counted separately on the badge
   ("+N author"). Author runs seed the network; they don't inflate
   the independence number.
3. **Everything is public.** Timestamps, hardware fingerprints, pubkeys,
   observed metrics — all in the open, forever. A fake attestation is
   a signed lie attached to your name and key, in public, permanently.
   Social cost is the actual deterrent, and the ledger maximizes it.
4. **Hardware diversity is shown, not just counted.** `repro log`
   lists the CPU/GPU strings seen. Five attestations from the same
   "Intel(R) Xeon(R) CPU" in the same hour read differently than five
   across vendors and weeks — and the reader can see which it is.
5. **PR identity is a second leg.** Ledger appends go through GitHub
   PRs, so each attestation file is also bound to a GitHub account.
   Burning a sock-puppet means burning a GitHub account per key.

## Known attacks we accept (for now)

| attack | why we accept it | future mitigation |
|---|---|---|
| Verifier fakes metrics without running | undetectable by design; social cost only | optional TEE/remote-attestation mode |
| Sock-puppet keys | visible in the open log; readers judge | proof-of-personhood / stake |
| Recipe author ships a rigged recipe (command always PASSes) | recipes are public; the command is inspectable — a rigged recipe is a public embarrassment | community recipe review; "verified command" flag after independent audit |
| Commit pinning bypass via `--no-clone` | result records `code_pinned: false`; attestations SHOULD note it — verifiers are expected to use clean clones | CI check that attestations reference pinned runs |

## What this is NOT

- Not a replacement for SLSA/Sigstore (provenance: *who built it*).
  reproledger answers the complementary question: *can anyone else
  rebuild it and get the same numbers?* Use both.
- Not a benchmark leaderboard. benchshield audits benchmark
  *integrity*; reproledger attests *reproducibility*. A result can
  be reproducible and still cherry-picked — that's benchshield's beat.
