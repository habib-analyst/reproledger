"""Canonical JSON + hashing. The foundation every signature and recipe
identity rests on: two machines must compute the same hash for the same
logical document, regardless of key order or whitespace."""

import hashlib
import json


def canonical(obj) -> bytes:
    """Canonical byte representation: sorted keys, no whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(obj) -> str:
    """SHA-256 hex digest of the canonical form of obj."""
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha256_file_hex(path, chunk=65536) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()
