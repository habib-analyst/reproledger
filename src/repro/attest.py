"""Signed attestations: the unit of the public log.

A verifier who gets PASS runs `repro attest` to mint a signed attestation:
a JSON document bound to the recipe hash, the observed metrics, the
hardware fingerprint, and the verifier's identity — signed with their SSH
key (ssh-keygen -Y, the same primitive GitHub uses for signed commits).

Design choice, stated plainly: SSH signatures are standard, every
developer already has a key, and verification needs no keyserver. The
ledger (a GitHub repo) additionally binds each attestation file to a PR
author, so identity has two independent legs: the signature and the PR.
"""

import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical, sha256_hex
from .recipe import recipe_hash

SIGN_NAMESPACE = "reproledger-attest-v1"
FINGERPRINT_RE = re.compile(r"SHA256:([A-Za-z0-9+/=]+)")


class AttestError(RuntimeError):
    pass


def _need_ssh_keygen():
    if shutil.which("ssh-keygen") is None:
        raise AttestError("ssh-keygen is required for signing attestations")
    if shutil.which("ssh-agent") is None and False:  # placeholder, no agent needed
        pass


def pubkey_fingerprint(pubkey_line: str) -> str:
    """SHA256 fingerprint of an SSH public key line, OpenSSH format."""
    _need_ssh_keygen()
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as f:
        f.write(pubkey_line.strip() + "\n")
        path = f.name
    p = subprocess.run(["ssh-keygen", "-lf", path], stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, text=True)
    Path(path).unlink(missing_ok=True)
    if p.returncode != 0:
        raise AttestError(f"not a valid SSH public key: {p.stderr.strip()[:200]}")
    m = FINGERPRINT_RE.search(p.stdout)
    if not m:
        raise AttestError("could not parse key fingerprint")
    return "SHA256:" + m.group(1)


def sign_message(message: bytes, key_path: str) -> str:
    """Sign bytes with an SSH private key. Returns armored signature text."""
    _need_ssh_keygen()
    p = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", key_path,
                        "-n", SIGN_NAMESPACE],
                       input=message, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise AttestError(f"ssh-keygen sign failed: "
                          f"{p.stderr.decode()[:300]}")
    return p.stdout.decode()


def verify_signature(message: bytes, armored_sig: str, pubkey_line: str,
                     principal: str) -> bool:
    """Verify an armored SSH signature against a public key line."""
    _need_ssh_keygen()
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as kf:
        kf.write(f"{principal.strip()} {pubkey_line.strip()}\n")
        keyfile = kf.name
    with tempfile.NamedTemporaryFile("w", delete=False) as sf:
        sf.write(armored_sig if armored_sig.endswith("\n") else armored_sig + "\n")
        sigfile = sf.name
    try:
        p = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", keyfile,
                            "-I", principal.strip(), "-n", SIGN_NAMESPACE,
                            "-s", sigfile],
                           input=message, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
        return p.returncode == 0
    finally:
        Path(keyfile).unlink(missing_ok=True)
        Path(sigfile).unlink(missing_ok=True)


def build_attestation(verify_result, recipe, verifier_name, verifier_contact,
                      key_path, self_attested=False):
    """Mint a signed attestation from a PASS verify result."""
    if verify_result.get("verdict") != "PASS":
        raise AttestError("refusing to attest a non-PASS result — "
                          "the log records reproductions, not attempts")
    pubkey_line = Path(key_path + ".pub").read_text().strip().splitlines()[0]
    fingerprint = pubkey_fingerprint(pubkey_line)
    body = {
        "reproledger": "1.0",
        "kind": "attestation",
        "recipe_name": recipe["name"],
        "recipe_hash": recipe_hash(recipe),
        "verifier": {"name": verifier_name, "contact": verifier_contact,
                     "pubkey_fingerprint": fingerprint},
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "result": "PASS",
        "metrics_observed": verify_result["metrics_observed"],
        "metrics_expected": verify_result["metrics_expected"],
        "environment_observed": verify_result["environment_observed"],
        "repro_version": verify_result.get("repro_version", "?"),
        "self_attested": bool(self_attested),
        "notes": "",
    }
    sig = sign_message(canonical(body), key_path)
    attestation = dict(body)
    attestation["signature"] = {"scheme": "ssh",
                                "namespace": SIGN_NAMESPACE,
                                "pubkey": pubkey_line,
                                "sig": sig}
    return attestation


def check_attestation(att):
    """Verify an attestation's internal consistency + signature.

    Returns (ok, errors: list). Checks: schema fields present, recipe hash
    matches the embedded recipe reference implicitly (checked by caller
    against the ledger's recipe file), signature valid, fingerprint matches
    the embedded pubkey.
    """
    errors = []
    for f in ("reproledger", "kind", "recipe_name", "recipe_hash",
              "verifier", "timestamp", "result", "signature"):
        if f not in att:
            errors.append(f"missing field '{f}'")
    if errors:
        return False, errors
    if att.get("kind") != "attestation":
        errors.append("kind != attestation")
    sig = att["signature"]
    try:
        fp = pubkey_fingerprint(sig["pubkey"])
    except AttestError as e:
        return False, [f"bad pubkey: {e}"]
    if fp != att["verifier"].get("pubkey_fingerprint"):
        errors.append("pubkey fingerprint does not match verifier record")
    body = {k: v for k, v in att.items() if k != "signature"}
    principal = att["verifier"].get("contact") or att["verifier"].get("name", "")
    if not verify_signature(canonical(body), sig["sig"], sig["pubkey"], principal):
        errors.append("SSH signature INVALID")
    return (len(errors) == 0), errors


def dump_attestation(att, path):
    Path(path).write_text(json.dumps(att, indent=2) + "\n")
