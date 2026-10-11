"""Test suite for reproledger. Run: pytest -q"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from repro import recipe as R
from repro import metrics as M
from repro import canonical as C
from repro import ledger as L
from repro import badge as B

GOOD = {
    "reproledger": "1.0",
    "name": "toy-suite",
    "title": "Toy test suite",
    "author": {"name": "Test", "url": "https://example.com"},
    "code": {"repo": "https://github.com/example/toy",
             "commit": "a" * 40, "subdir": "."},
    "data": [{"name": "d.csv", "sha256": "b" * 64,
              "url": "https://example.com/d.csv"}],
    "environment": {"python": ">=3.10"},
    "command": "python -m pytest tests/ -q",
    "metrics_file": "repro_metrics.json",
    "metrics": {
        "tests_passed": {"expected": 5, "tolerance": 0, "compare": "ge"},
        "accuracy": {"expected": 0.9, "tolerance": 0.01},
    },
    "timeout_s": 300,
}


def test_recipe_validates():
    r = R.validate(GOOD)
    assert r["name"] == "toy-suite"
    assert r["metrics"]["accuracy"]["compare"] == "within"  # default


def test_recipe_hash_deterministic():
    assert R.recipe_hash(GOOD) == R.recipe_hash(dict(GOOD))
    other = dict(GOOD, name="other")
    assert R.recipe_hash(other) != R.recipe_hash(GOOD)


@pytest.mark.parametrize("bad", [
    dict(GOOD, reproledger="9.9"),
    dict(GOOD, name="Bad Name!"),
    dict(GOOD, code={"repo": "https://x", "commit": "abc"}),
    dict(GOOD, code={"repo": "https://x", "commit": "a" * 40},
         metrics={}),
    dict(GOOD, metrics={"m": {"expected": 1, "compare": "bogus"}}),
    dict(GOOD, metrics={"m": {"expected": 1, "tolerance": -1}}),
    dict(GOOD, command="   "),
    dict(GOOD, metrics_file="/abs/path.json"),
    dict(GOOD, timeout_s=0),
])
def test_recipe_rejects_bad(bad):
    with pytest.raises(R.RecipeError):
        R.validate(bad)


def test_canonical_stable():
    a = {"b": 1, "a": [1, 2]}
    b = {"a": [1, 2], "b": 1}
    assert C.canonical(a) == C.canonical(b)
    assert C.sha256_hex(a) == C.sha256_hex(b)


@pytest.mark.parametrize("observed,spec,ok", [
    (0.905, {"expected": 0.9, "tolerance": 0.01, "compare": "within"}, True),
    (0.92, {"expected": 0.9, "tolerance": 0.01, "compare": "within"}, False),
    (13, {"expected": 13, "tolerance": 0, "compare": "ge"}, True),
    (12, {"expected": 13, "tolerance": 0, "compare": "ge"}, False),
    (12, {"expected": 13, "tolerance": 1, "compare": "ge"}, True),
    (0.5, {"expected": 0.9, "tolerance": 0.5, "compare": "le"}, True),
    (1, {"expected": 1, "tolerance": 0, "compare": "exact"}, True),
    (2, {"expected": 1, "tolerance": 0, "compare": "exact"}, False),
    ("x", {"expected": 1, "tolerance": 0, "compare": "within"}, False),
    (float("nan"), {"expected": 1, "tolerance": 9, "compare": "within"}, False),
])
def test_compare_modes(observed, spec, ok):
    assert M.compare(observed, spec)[0] is ok


def test_compare_all_missing_metric():
    verdict, rows = M.compare_all({}, R.validate(GOOD))
    assert verdict == "FAIL"
    assert all(r["observed"] is None for r in rows)


def _write_toy_project(tmp: Path):
    proj = tmp / "proj"
    proj.mkdir()
    (proj / "test_toy.py").write_text(
        "import json\n"
        "def test_a(): assert True\n"
        "def test_b(): assert True\n")
    return proj


def test_verify_pass_end_to_end(tmp_path):
    from repro.runner import verify
    proj = _write_toy_project(tmp_path)
    recipe = dict(GOOD)
    recipe["code"] = {"repo": "https://github.com/example/toy",
                      "commit": "a" * 40}
    recipe["command"] = (f"{sys.executable} -c \"import json; "
                         "json.dump({'tests_passed': 6, 'accuracy': 0.905}, "
                         "open('repro_metrics.json','w'))\"")
    recipe["data"] = []
    rp = tmp_path / "recipe.json"
    rp.write_text(json.dumps(recipe))
    wd = tmp_path / "ws" / "code"
    wd.mkdir(parents=True)
    # --no-clone: put a fake git repo? simpler: use no_clone with plain dir
    res = verify(str(rp), workdir=str(tmp_path / "ws"), no_clone=True)
    assert res["verdict"] == "PASS", res
    assert res["code_pinned"] is False  # plain dir, identity unpinned
    assert res["metrics_observed"]["tests_passed"] == 6


def test_verify_fail_on_metric_miss(tmp_path):
    from repro.runner import verify
    recipe = dict(GOOD)
    recipe["command"] = (f"{sys.executable} -c \"import json; "
                         "json.dump({'tests_passed': 2, 'accuracy': 0.5}, "
                         "open('repro_metrics.json','w'))\"")
    recipe["data"] = []
    rp = tmp_path / "recipe.json"
    rp.write_text(json.dumps(recipe))
    wd = tmp_path / "ws" / "code"
    wd.mkdir(parents=True)
    res = verify(str(rp), workdir=str(tmp_path / "ws"), no_clone=True)
    assert res["verdict"] == "FAIL"
    assert any(not r["ok"] for r in res["metric_rows"])


def test_verify_fail_on_bad_command(tmp_path):
    from repro.runner import verify
    recipe = dict(GOOD)
    recipe["command"] = f"{sys.executable} -c \"import sys; sys.exit(3)\""
    recipe["data"] = []
    rp = tmp_path / "recipe.json"
    rp.write_text(json.dumps(recipe))
    wd = tmp_path / "ws" / "code"
    wd.mkdir(parents=True)
    res = verify(str(rp), workdir=str(tmp_path / "ws"), no_clone=True)
    assert res["verdict"] == "FAIL"
    assert "rc=3" in res["failure"]


def test_verify_fail_missing_metrics_file(tmp_path):
    from repro.runner import verify
    recipe = dict(GOOD)
    recipe["command"] = f"{sys.executable} -c \"pass\""
    recipe["data"] = []
    rp = tmp_path / "recipe.json"
    rp.write_text(json.dumps(recipe))
    wd = tmp_path / "ws" / "code"
    wd.mkdir(parents=True)
    res = verify(str(rp), workdir=str(tmp_path / "ws"), no_clone=True)
    assert res["verdict"] == "FAIL"
    assert "metrics file" in res["failure"]


SSH = shutil.which("ssh-keygen")
needs_ssh = pytest.mark.skipif(not SSH, reason="ssh-keygen not available")


@needs_ssh
def test_attestation_round_trip(tmp_path):
    from repro import attest as A
    key = tmp_path / "id_ed25519"
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key),
                    "-q"], check=True)
    pub = (tmp_path / "id_ed25519.pub").read_text().strip()
    fp = A.pubkey_fingerprint(pub)
    assert fp.startswith("SHA256:")
    msg = b'{"hello": "world"}'
    sig = A.sign_message(msg, str(key))
    assert "SSH SIGNATURE" in sig
    assert A.verify_signature(msg, sig, pub.split()[0] + " " + pub.split()[1],
                              "tester")
    assert not A.verify_signature(b'{"hello": "tampered"}', sig,
                                  pub.split()[0] + " " + pub.split()[1],
                                  "tester")


@needs_ssh
def test_attestation_check_and_ledger(tmp_path):
    from repro import attest as A
    key = tmp_path / "id_ed25519"
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key),
                    "-q"], check=True)
    recipe = R.validate(GOOD)
    vres = {"verdict": "PASS",
            "metrics_observed": {"tests_passed": 6, "accuracy": 0.905},
            "metrics_expected": {"tests_passed": {"expected": 5},
                                 "accuracy": {"expected": 0.9}},
            "environment_observed": {"cpu": "test-cpu", "gpu": "none"},
            "repro_version": "0.1.0"}
    att = A.build_attestation(vres, recipe, "Tester", "github:tester",
                              str(key))
    ok, errors = A.check_attestation(att)
    assert ok, errors
    # tamper -> invalid
    bad = dict(att)
    bad["metrics_observed"] = {"tests_passed": 600, "accuracy": 0.905}
    ok2, _ = A.check_attestation(bad)
    assert not ok2
    # ledger round trip
    led = L.Ledger(tmp_path / "ledger")
    led.add_recipe(recipe)
    led.add_attestation(att)
    summ = led.summary("toy-suite")
    assert summ["toy-suite"]["parties"] == 1
    assert summ["toy-suite"]["attestations"] == 1
    # second key, same recipe -> 2 parties; author self-attest counted apart
    key2 = tmp_path / "id2"
    subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key2),
                    "-q"], check=True)
    att2 = A.build_attestation(vres, recipe, "Tester2", "github:tester2",
                               str(key2))
    led.add_attestation(att2)
    att3 = A.build_attestation(vres, recipe, "Author", "github:author",
                               str(key), self_attested=True)
    led.add_attestation(att3)
    summ = led.summary("toy-suite")
    assert summ["toy-suite"]["parties"] == 2
    assert summ["toy-suite"]["self_attested"] == 1
    assert summ["toy-suite"]["attestations"] == 3


def test_prepare_data_hash_check(tmp_path):
    import hashlib
    from repro.runner import prepare_data, VerifyError
    dataf = tmp_path / "d.csv"
    dataf.write_bytes(b"a,b\n1,2\n")
    h = hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    recipe = {"data": [{"name": "d.csv", "sha256": h}]}
    with pytest.raises(VerifyError):  # missing file, no URL -> error
        prepare_data(recipe, tmp_path / "ws")
    # place the file with the right hash -> passes
    (tmp_path / "ws" / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ws" / "data" / "d.csv").write_bytes(b"a,b\n1,2\n")
    prepare_data(recipe, tmp_path / "ws")
    # tampered file -> mismatch
    (tmp_path / "ws" / "data" / "d.csv").write_bytes(b"a,b\n1,3\n")
    with pytest.raises(VerifyError):
        prepare_data(recipe, tmp_path / "ws")


def test_run_command_uses_venv(tmp_path):
    from repro.runner import run_command
    recipe = {"command": f"{sys.executable} -c \"pass\"",
              "timeout_s": 120,
              "environment": {"setup": "pip install -q six"}}
    rundir = tmp_path / "code"
    rundir.mkdir(parents=True)
    run = run_command(recipe, rundir, tmp_path)
    assert run["rc"] == 0, run["stderr"][-300:]
    assert run["used_venv"] is True
    assert (tmp_path / "venv" / "bin" / "pip").exists()


def test_target_python_prefers_venv(tmp_path, monkeypatch):
    from repro.pytest_helper import _target_python
    import os
    ve = tmp_path / "ve"
    (ve / "bin").mkdir(parents=True)
    (ve / "bin" / "python").write_text("#!/bin/sh\n")
    monkeypatch.setenv("VIRTUAL_ENV", str(ve))
    assert _target_python() == str(ve / "bin" / "python")
    monkeypatch.delenv("VIRTUAL_ENV")
    assert _target_python()  # falls back to something runnable


def test_badge_svg_content():
    svg = B.badge_svg("toy-suite", 0, 0, 0)
    assert "not yet reproduced" in svg and "<svg" in svg
    svg = B.badge_svg("toy-suite", 1, 0, 1)
    assert "1 independent party" in svg
    svg = B.badge_svg("toy-suite", 0, 2, 2)
    assert "author-verified" in svg
    svg = B.badge_svg("toy-suite", 5, 1, 9)
    assert "5 independent parties" in svg and "+1 author" in svg
