"""Minimal static HTML rendering of version-pair diffs.

Output contains change excerpts only (deleted/inserted token runs), never a
verbatim reconstruction of a full rulebook.
"""

from __future__ import annotations

import html
import json
import os

from .diff import diff_extractions
from .extract import extract

SITE_DIR = "site"

_CSS = """
body{font-family:ui-monospace,Consolas,monospace;max-width:60em;margin:2em auto;padding:0 1em;color:#222}
a{color:#0366d6} del{background:#fdd;text-decoration:line-through;color:#a00}
ins{background:#dfd;text-decoration:none;color:#060}
.art{border:1px solid #ccc;border-radius:6px;padding:.6em 1em;margin:1em 0}
.art h3{margin:.2em 0}
.op{font-size:.9em;margin:.4em 0;padding-left:1em;border-left:3px solid #eee}
.meta{color:#666;font-size:.85em}
"""

MAX_OPS_SHOWN = 60


def _op_html(op: dict) -> str:
    d = " ".join(op.get("del", []))
    i = " ".join(op.get("ins", []))
    return f'<div class="op"><del>{html.escape(d)}</del> <ins>{html.escape(i)}</ins></div>'


def _pair_page(m: dict, res: dict, titles: dict) -> str:
    fa, fb = res["from_version"], res["to_version"]
    parts = [
        "<!doctype html><meta charset=utf-8>",
        f"<title>BME MTF Equity v{fa} → v{fb}</title>",
        f"<style>{_CSS}</style>",
        f"<h1>BME MTF Equity Rulebook — v{fa} → v{fb}</h1>",
        '<p><a href="index.html">all comparisons</a></p>',
        f'<p class="meta">{len(res["changed_articles"])} articles changed'
        + (", Final Provision changed" if res["final_provision_changed"] else "")
        + "</p>",
    ]
    if res.get("global_change_events"):
        parts.append("<h2>Global change events</h2><ul>")
        for e in res["global_change_events"]:
            parts.append(
                f'<li><code>{" ".join(e["del"])} → {" ".join(e["ins"])}</code>'
                f' — articles {e["articles"]}</li>')
        parts.append("</ul>")
    for c in res["changes"]:
        a = c["article"]
        label = "Final Provision" if a == "FINAL" else f"Article {a}"
        title = titles.get(str(a), "")
        cls = f' <span class="meta">[{c["change_class"]}]</span>' \
            if c.get("change_class") else ""
        parts.append(f'<div class="art"><h3>{label} — {c["status"]}{cls}</h3>'
                     f'<div class="meta">{html.escape(title)}</div>')
        for g in c.get("global_changes", []):
            parts.append(f'<div class="meta">global: {html.escape(g)}</div>')
        ops = c.get("diff", [])
        for op in ops[:MAX_OPS_SHOWN]:
            parts.append(_op_html(op))
        if len(ops) > MAX_OPS_SHOWN:
            parts.append(f'<div class="meta">… {len(ops)-MAX_OPS_SHOWN} more ops</div>')
        parts.append("</div>")
    return "\n".join(parts)


def build_site(manifest: dict, pairs: list[tuple[str, str]],
               site_dir: str = SITE_DIR) -> str:
    os.makedirs(site_dir, exist_ok=True)
    index_rows = []
    for fa, fb in pairs:
        ea = next(v for v in manifest["versions"] if v["version"] == fa)
        eb = next(v for v in manifest["versions"] if v["version"] == fb)
        exa = extract(ea["local_file"])
        exb = extract(eb["local_file"])
        res = diff_extractions(exa, exb, {
            "from_version": fa, "to_version": fb,
            "source_hashes": {"from": ea["sha256"], "to": eb["sha256"]}})
        titles = {str(n): t for n, t in exb.toc}
        page = f"v{fa}_v{fb}.html"
        with open(os.path.join(site_dir, page), "w", encoding="utf-8") as f:
            f.write(_pair_page(manifest, res, titles))
        with open(os.path.join(site_dir, f"v{fa}_v{fb}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        n = len(res["changed_articles"])
        index_rows.append(
            f'<li><a href="{page}">v{fa} → v{fb}</a>: {n} articles changed '
            f'({ea["approval_date"]} → {eb["approval_date"]})</li>')
    index = (
        "<!doctype html><meta charset=utf-8>"
        "<title>venue-rule-diff — BME MTF Equity</title>"
        f"<style>{_CSS}</style>"
        "<h1>venue-rule-diff — BME MTF Equity Rulebook</h1>"
        f'<p class="meta">Successive official versions. '
        f'Source SHA-256 and provenance in manifests/bme_mtf_equity.json.</p>'
        f"<ul>{''.join(index_rows)}</ul>")
    with open(os.path.join(site_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(index)
    return site_dir
