"""Reproducible retrieval of official source documents.

Downloads each manifest version's ``source_url`` into ``data/raw/``,
computes SHA-256 and refreshes the manifest's ``retrieved_at`` /
``sha256`` provenance fields.  ``retrieved_at`` is volatile metadata and
is excluded from deterministic comparisons.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import urllib.request

MANIFEST = os.path.join("manifests", "bme_mtf_equity.json")
RAW_DIR = os.path.join("data", "raw")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: str = MANIFEST) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch(version: str, manifest_path: str = MANIFEST) -> dict:
    m = load_manifest(manifest_path)
    entry = next(v for v in m["versions"] if v["version"] == str(version))
    url = entry["retrieved_from"] or entry["source_url"]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
    sha = hashlib.sha256(body).hexdigest()
    if not body.startswith(b"%PDF-"):
        raise ValueError(f"{url} did not return a PDF "
                         f"({r.headers.get('Content-Type')})")
    os.makedirs(RAW_DIR, exist_ok=True)
    local = entry.get("local_file") or os.path.join(
        RAW_DIR, f"bme_mtf_equity_v{version}.pdf")
    with open(local, "wb") as f:
        f.write(body)
    entry["retrieved_at"] = ts
    entry["sha256"] = sha
    entry["local_file"] = local
    return entry


def verify_local(entry: dict) -> bool:
    """True if the local file's sha256 matches the manifest provenance."""
    local = entry.get("local_file")
    return bool(local and os.path.exists(local)
                and sha256_file(local) == entry["sha256"])
