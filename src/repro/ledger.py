"""The ledger: a local working copy of the public log.

On the network the ledger IS this repo's ledger/ directory: PRs append
  ledger/recipes/<name>/recipe.json
  ledger/attestations/<recipe-hash12>/<timestamp>-<slug>.json
`repro log` reads any checkout of it and answers: what is reproduced, by
whom, on what hardware. `repro badge` turns that into an SVG.

Counting rule (the anti-gaming core): an "independent party" is a distinct
SSH-key fingerprint. Ten attestations from one key = one party. The
recipe author's own attestations are labeled self-attested and counted
separately — the badge shows both numbers, so readers judge for
themselves. See docs/THREAT_MODEL.md for the honest limits.
"""

import json
import re
from datetime import datetime
from pathlib import Path

SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(s):
    return SLUG_RE.sub("-", s.lower()).strip("-")[:40] or "anon"


class Ledger:
    def __init__(self, root):
        self.root = Path(root)
        self.recipes_dir = self.root / "recipes"
        self.att_dir = self.root / "attestations"

    # ---- writes ------------------------------------------------------
    def add_recipe(self, recipe):
        from .recipe import dump as dump_recipe, recipe_hash
        d = self.recipes_dir / recipe["name"]
        d.mkdir(parents=True, exist_ok=True)
        dump_recipe(recipe, d / "recipe.json")
        return d / "recipe.json"

    def add_attestation(self, att):
        ts = att["timestamp"].replace(":", "").replace("+0000", "Z")
        fname = f"{ts}-{slugify(att['verifier']['name'])}.json"
        d = self.att_dir / att["recipe_hash"][:12]
        d.mkdir(parents=True, exist_ok=True)
        from .attest import dump_attestation
        dump_attestation(att, d / fname)
        return d / fname

    # ---- reads -------------------------------------------------------
    def recipes(self):
        out = {}
        if not self.recipes_dir.is_dir():
            return out
        for d in sorted(self.recipes_dir.iterdir()):
            f = d / "recipe.json"
            if f.exists():
                try:
                    out[d.name] = json.loads(f.read_text())
                except json.JSONDecodeError:
                    continue
        return out

    def attestations(self, recipe_hash=None):
        out = []
        if not self.att_dir.is_dir():
            return out
        dirs = [self.att_dir / recipe_hash[:12]] if recipe_hash else \
            sorted(self.att_dir.iterdir())
        for d in dirs:
            if not d.is_dir():
                continue
            for f in sorted(d.glob("*.json")):
                try:
                    out.append(json.loads(f.read_text()))
                except json.JSONDecodeError:
                    continue
        return out

    def summary(self, recipe_name=None):
        """Per-recipe reproduction summary.

        Returns {recipe_name: {parties, attestations, self_attested,
        hardware: [...], first_seen, last_seen}}.
        """
        recipes = self.recipes()
        if recipe_name:
            recipes = {k: v for k, v in recipes.items() if k == recipe_name}
        from .recipe import recipe_hash as rhash
        hash_by_name = {n: rhash(r) for n, r in recipes.items()}
        name_by_hash = {h: n for n, h in hash_by_name.items()}
        summary = {n: {"parties": 0, "attestations": 0, "self_attested": 0,
                       "hardware": [], "first_seen": None, "last_seen": None,
                       "title": r.get("title", "")}
                   for n, r in recipes.items()}
        for att in self.attestations():
            n = name_by_hash.get(att.get("recipe_hash", ""))
            if n is None or n not in summary:
                continue
            s = summary[n]
            s["attestations"] += 1
            if att.get("self_attested"):
                s["self_attested"] += 1
            else:
                fp = att.get("verifier", {}).get("pubkey_fingerprint", "?")
                s.setdefault("_fps", set()).add(fp)
            hw = att.get("environment_observed", {}).get("cpu", "?")
            if hw not in s["hardware"]:
                s["hardware"].append(hw)
            ts = att.get("timestamp", "")
            if not s["first_seen"] or ts < s["first_seen"]:
                s["first_seen"] = ts
            if not s["last_seen"] or ts > s["last_seen"]:
                s["last_seen"] = ts
        for s in summary.values():
            s["parties"] = len(s.pop("_fps", set()))
        return summary
