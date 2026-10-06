"""Command line interface.

    python -m src.cli validate <version>     G1 structural gate on one version
    python -m src.cli compare <from> <to>    article diff (JSON to stdout)
    python -m src.cli report <from> <to>     human-readable report
    python -m src.cli site                   generate site/index.html for all
                                             successive version pairs
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import io

from .diff import diff_extractions, human_report

# Windows consoles default to cp1252; emit UTF-8 unconditionally
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                  errors="replace")
from .download import load_manifest, verify_local
from .extract import extract
from .validate import validate_extraction


def _entry(m: dict, version: str) -> dict:
    return next(v for v in m["versions"] if v["version"] == str(version))


def _load_version(entry: dict, ocr: bool = True):
    local = entry["local_file"]
    if not os.path.exists(local):
        raise SystemExit(f"missing source file {local} — run download first")
    ok_hash = verify_local(entry)
    ex = extract(local, ocr=ocr)
    return ex, ok_hash


def cmd_validate(args):
    m = load_manifest()
    entry = _entry(m, args.version)
    ex, ok_hash = _load_version(entry, ocr=not args.no_ocr)
    res = validate_extraction(ex)
    res["version"] = args.version
    res["sha256_ok"] = ok_hash
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0 if res["g1_pass"] else 1


def _pair(args):
    m = load_manifest()
    ea, eb = _entry(m, args.from_version), _entry(m, args.to_version)
    exa, ha = _load_version(ea, ocr=not args.no_ocr)
    exb, hb = _load_version(eb, ocr=not args.no_ocr)
    meta = {
        "from_version": ea["version"],
        "to_version": eb["version"],
        "source_hashes": {"from": ea["sha256"], "to": eb["sha256"]},
        "hash_check": {"from": ha, "to": hb},
    }
    res = diff_extractions(exa, exb, meta)
    titles = {str(n): t for n, t in exb.toc}
    return res, titles


def cmd_compare(args):
    res, _ = _pair(args)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    return 0


def cmd_report(args):
    res, titles = _pair(args)
    print(human_report(res, titles))
    return 0


def cmd_toolchain(args):
    from .extract import toolchain_info
    print(json.dumps(toolchain_info(), indent=2, ensure_ascii=False))
    return 0


def cmd_site(args):
    from .sitegen import build_site
    m = load_manifest()
    versions = [v["version"] for v in m["versions"]]
    pairs = list(zip(versions, versions[1:]))
    out = build_site(m, pairs)
    print(f"site written to {out}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="venue-rule-diff")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("validate", "compare", "report", "site", "toolchain"):
        sp = sub.add_parser(name)
        if name in ("compare", "report"):
            sp.add_argument("from_version")
            sp.add_argument("to_version")
        if name == "validate":
            sp.add_argument("version")
        sp.add_argument("--no-ocr", action="store_true",
                        help="disable OCR fallback for image-rendered headings")
        sp.set_defaults(func=globals()[f"cmd_{name}"])
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
