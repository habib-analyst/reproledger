"""Metric comparison semantics — the tolerance logic that decides
whether a reproduction counts."""

import math


def compare(observed, spec):
    """Return (ok: bool, detail: str) for one metric.

    spec: {"expected": x, "tolerance": t, "compare": mode}
    modes: within (|o-e|<=t), ge (o>=e-t), le (o<=e+t), exact (o==e)
    """
    exp, tol, mode = spec["expected"], spec["tolerance"], spec["compare"]
    if not isinstance(observed, (int, float)) or isinstance(observed, bool):
        return False, f"observed value {observed!r} is not a number"
    if isinstance(observed, float) and (math.isnan(observed) or math.isinf(observed)):
        return False, f"observed value {observed!r} is not finite"
    if mode == "within":
        ok = abs(observed - exp) <= tol
        detail = f"|{observed} - {exp}| = {abs(observed - exp):.6g} <= {tol}"
    elif mode == "ge":
        ok = observed >= exp - tol
        detail = f"{observed} >= {exp} - {tol}"
    elif mode == "le":
        ok = observed <= exp + tol
        detail = f"{observed} <= {exp} + {tol}"
    elif mode == "exact":
        ok = observed == exp
        detail = f"{observed} == {exp}"
    else:  # pragma: no cover — schema validation forbids this
        raise ValueError(f"unknown compare mode {mode!r}")
    return ok, detail


def compare_all(observed_metrics, recipe):
    """Compare every recipe metric. Returns (verdict, rows).

    verdict: "PASS" if all metrics ok, else "FAIL".
    rows: list of dicts {metric, expected, observed, tolerance, compare, ok, detail}
    """
    rows, all_ok = [], True
    for name, spec in recipe["metrics"].items():
        if name not in observed_metrics:
            rows.append({"metric": name, "expected": spec["expected"],
                         "observed": None, "tolerance": spec["tolerance"],
                         "compare": spec["compare"], "ok": False,
                         "detail": "metric missing from metrics file"})
            all_ok = False
            continue
        ok, detail = compare(observed_metrics[name], spec)
        rows.append({"metric": name, "expected": spec["expected"],
                     "observed": observed_metrics[name],
                     "tolerance": spec["tolerance"], "compare": spec["compare"],
                     "ok": ok, "detail": detail})
        all_ok = all_ok and ok
    return ("PASS" if all_ok else "FAIL"), rows
