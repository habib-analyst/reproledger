"""`repro` CLI."""

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .attest import (AttestError, build_attestation, check_attestation,
                     dump_attestation)
from .badge import badge_svg
from .ledger import Ledger
from .recipe import RecipeError, dump as dump_recipe, load as load_recipe, recipe_hash, validate


def cmd_publish(a):
    recipe = load_recipe(a.recipe)
    dest = Path(a.out) if a.out else Path("recipe.json")
    dump_recipe(recipe, dest)
    h = recipe_hash(recipe)
    print(f"recipe '{recipe['name']}' validated (schema v{recipe['reproledger']})")
    print(f"recipe hash: {h}")
    print(f"wrote {dest}")
    print("next: open a PR adding it to ledger/recipes/<name>/recipe.json")


def cmd_verify(a):
    from .runner import verify
    res = verify(a.recipe, workdir=a.workdir, no_clone=a.no_clone, keep=a.keep)
    if a.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"recipe:  {res['recipe_name']}  ({res['recipe_hash'][:12]}…)")
        print(f"verdict: {res['verdict']}")
        for row in res.get("metric_rows", []):
            mark = "ok" if row["ok"] else "MISS"
            print(f"  [{mark}] {row['metric']}: observed={row['observed']} "
                  f"expected={row['expected']} ±{row['tolerance']} "
                  f"({row['compare']}) — {row['detail']}")
        if res.get("failure"):
            print(f"failure: {res['failure']}")
        print(f"elapsed: {res.get('elapsed_s', '?')}s")
    if a.attest:
        if res["verdict"] != "PASS":
            sys.exit("cannot attest a non-PASS result")
        att = build_attestation(res, load_recipe(a.recipe), a.name, a.contact,
                                a.key, self_attested=a.self_attest)
        out = Path(a.attest_out or
                   f"attestation-{res['recipe_hash'][:12]}.json")
        dump_attestation(att, out)
        print(f"signed attestation -> {out}")
        print("next: open a PR adding it under "
              f"ledger/attestations/{res['recipe_hash'][:12]}/")
    sys.exit(0 if res["verdict"] == "PASS" else 1)


def cmd_log(a):
    led = Ledger(a.ledger)
    summ = led.summary(a.recipe)
    if not summ:
        print("ledger is empty — no recipes published yet")
        return
    for name, s in summ.items():
        print(f"{name}: {s['title']}")
        print(f"  reproduced by {s['parties']} independent "
              f"{'party' if s['parties'] == 1 else 'parties'}"
              f"{f' (+{s['self_attested']} author-verified)' if s['self_attested'] else ''} "
              f"· {s['attestations']} attestations")
        if s["hardware"]:
            print(f"  hardware seen: {'; '.join(s['hardware'][:3])}")
        if s["first_seen"]:
            print(f"  first: {s['first_seen'][:10]} · last: {s['last_seen'][:10]}")


def cmd_badge(a):
    led = Ledger(a.ledger)
    summ = led.summary(a.recipe)
    if a.recipe not in summ:
        sys.exit(f"recipe '{a.recipe}' not in ledger")
    s = summ[a.recipe]
    svg = badge_svg(a.recipe, s["parties"], s["self_attested"], s["attestations"])
    Path(a.out).write_text(svg)
    print(f"badge -> {a.out} ({s['parties']} parties, "
          f"{s['self_attested']} self-attested)")


def cmd_check(a):
    att = json.loads(Path(a.attestation).read_text())
    ok, errors = check_attestation(att)
    if ok:
        print("attestation VALID: signature checks out")
    else:
        print("attestation INVALID:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)


def cmd_pytest(a):
    from .pytest_helper import run_pytest
    sys.exit(run_pytest(a.args, a.metrics_file))


def build_parser():
    p = argparse.ArgumentParser(
        prog="repro",
        description="reproledger: the reproducibility attestation network")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("publish", help="validate a recipe for publication")
    sp.add_argument("recipe", help="path to recipe.json")
    sp.add_argument("--out", help="where to write the normalized recipe")
    sp.set_defaults(fn=cmd_publish)

    sv = sub.add_parser("verify", help="re-run a recipe and check metrics")
    sv.add_argument("recipe", help="path (or URL) to recipe.json")
    sv.add_argument("--workdir", help="reuse a workspace dir (default: fresh temp)")
    sv.add_argument("--no-clone", action="store_true",
                    help="use <workdir>/code as-is instead of cloning")
    sv.add_argument("--keep", action="store_true", help="keep temp workspace")
    sv.add_argument("--json", action="store_true", help="machine-readable output")
    sv.add_argument("--attest", action="store_true",
                    help="mint a signed attestation on PASS")
    sv.add_argument("--name", default="", help="verifier display name")
    sv.add_argument("--contact", default="", help="verifier contact (e.g. github:user)")
    sv.add_argument("--key", default=str(Path.home() / ".ssh" / "id_ed25519"),
                    help="SSH private key for signing")
    sv.add_argument("--self-attest", action="store_true",
                    help="mark attestation as the recipe author's own run")
    sv.add_argument("--attest-out", help="attestation output path")
    sv.set_defaults(fn=cmd_verify)

    sl = sub.add_parser("log", help="query the attestation ledger")
    sl.add_argument("--ledger", default="ledger", help="ledger directory")
    sl.add_argument("--recipe", help="only this recipe")
    sl.set_defaults(fn=cmd_log)

    sb = sub.add_parser("badge", help="render the reproduction badge SVG")
    sb.add_argument("--ledger", default="ledger", help="ledger directory")
    sb.add_argument("--recipe", required=True, help="recipe name")
    sb.add_argument("--out", default="badge.svg", help="output SVG path")
    sb.set_defaults(fn=cmd_badge)

    sc = sub.add_parser("check", help="verify an attestation's signature")
    sc.add_argument("attestation", help="attestation JSON file")
    sc.set_defaults(fn=cmd_check)

    sy = sub.add_parser("pytest",
                        help="run pytest and write a metrics JSON "
                             "(for test-suite recipes)")
    sy.add_argument("args", nargs=argparse.REMAINDER, help="pytest args")
    sy.add_argument("--metrics-file", default="repro_metrics.json")
    sy.set_defaults(fn=cmd_pytest)
    return p


def main(argv=None):
    a = build_parser().parse_args(argv)
    try:
        a.fn(a)
    except (RecipeError, AttestError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
