"""Article-level alignment and diffing.

Alignment is strictly ``article_number -> article_number`` plus the Final
Provision.  No fuzzy matching, no renumbering.

Each aligned unit gets one structural status: UNCHANGED, MODIFIED, ADDED
or REMOVED.  MODIFIED units carry a deterministic word-level diff
(difflib.SequenceMatcher over word/punctuation tokens).  A separate
classification layer labels the change as substantive / terminology /
cross_reference / formatting / unknown without altering the raw diff.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter

from .extract import Extraction
from .normalize import normalize_text, tokenize

FINAL_KEY = "FINAL"

_REF_WORDS = {"artículo", "articulo", "artículos", "art.", "arts."}


def _align_keys(a: Extraction, b: Extraction) -> list[str]:
    keys = [str(n) for n in range(1, 48)]
    if a.final is not None or b.final is not None:
        keys.append(FINAL_KEY)
    return keys


def _text_of(ex: Extraction, key: str) -> str | None:
    if key == FINAL_KEY:
        return normalize_text(ex.final.text) if ex.final else None
    seg = ex.articles.get(int(key))
    return normalize_text(seg.text) if seg else None


def word_diff(a_text: str, b_text: str) -> list[dict]:
    """Deterministic word-level diff of two normalized texts."""
    ta, tb = tokenize(a_text), tokenize(b_text)
    sm = difflib.SequenceMatcher(a=ta, b=tb, autojunk=False)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        op = {"op": tag}
        if tag in ("delete", "replace"):
            op["del"] = ta[i1:i2]
        if tag in ("insert", "replace"):
            op["ins"] = tb[j1:j2]
        if tag == "equal":
            continue
        ops.append(op)
    return ops


def _change_pairs(ops: list[dict]) -> list[tuple[tuple, tuple]]:
    """(deleted-token-seq, inserted-token-seq) pairs from a word diff."""
    pairs = []
    for op in ops:
        d = tuple(op.get("del", []))
        i = tuple(op.get("ins", []))
        pairs.append((d, i))
    return pairs


def _is_formatting_only(ops: list[dict]) -> bool:
    """Every change affects only punctuation/casing-free tokens."""
    for op in ops:
        for t in op.get("del", []) + op.get("ins", []):
            if re.match(r"\w", t):
                return False
    return True


def _is_cross_reference_only(ops: list[dict]) -> bool:
    """All changed tokens are digits or article-reference markers."""
    for op in ops:
        for t in op.get("del", []) + op.get("ins", []):
            if t.isdigit() or t.lower() in _REF_WORDS:
                continue
            return False
    return bool(ops)


def _classify(ops: list[dict], global_pairs: set[tuple[tuple, tuple]]) -> str:
    if not ops:
        return "unknown"
    if _is_formatting_only(ops):
        return "formatting"
    if _is_cross_reference_only(ops):
        return "cross_reference"
    pairs = _change_pairs(ops)
    if pairs and all(p in global_pairs for p in pairs):
        return "terminology"
    return "substantive"


def diff_extractions(a: Extraction, b: Extraction,
                     meta: dict | None = None) -> dict:
    keys = _align_keys(a, b)
    changes: list[dict] = []
    texts: dict[str, tuple[str | None, str | None]] = {}
    statuses: dict[str, str] = {}

    for k in keys:
        ta, tb = _text_of(a, k), _text_of(b, k)
        texts[k] = (ta, tb)
        if ta is None and tb is None:
            statuses[k] = "UNCHANGED"
        elif ta is None:
            statuses[k] = "ADDED"
        elif tb is None:
            statuses[k] = "REMOVED"
        elif ta == tb:
            statuses[k] = "UNCHANGED"
        else:
            statuses[k] = "MODIFIED"

    # word diffs for modified units
    diffs: dict[str, list[dict]] = {}
    for k in keys:
        if statuses[k] == "MODIFIED":
            diffs[k] = word_diff(texts[k][0], texts[k][1])

    # global change events: identical token substitutions used in >1 unit
    pair_counter: Counter = Counter()
    for k, ops in diffs.items():
        for p in set(_change_pairs(ops)):
            pair_counter[p] += 1
    global_pairs = {p for p, c in pair_counter.items()
                    if c > 1 and p != ((), ())
                    and any(re.match(r"\w", t) for t in p[0] + p[1])}
    global_change_events = [
        {
            "del": list(d), "ins": list(i),
            "articles": sorted(
                (int(k) if k != FINAL_KEY else k) for k in diffs
                if pair in set(_change_pairs(diffs[k]))),
        }
        for pair, c in pair_counter.most_common()
        for (d, i) in [pair]
        if pair in global_pairs
    ]

    for k in keys:
        st = statuses[k]
        if st == "UNCHANGED":
            continue
        entry: dict = {
            "article": int(k) if k != FINAL_KEY else "FINAL",
            "status": st,
        }
        if st == "MODIFIED":
            ops = diffs[k]
            cls = _classify(ops, global_pairs)
            entry["change_class"] = cls
            entry["diff"] = ops
            for e in global_change_events:
                pair = (tuple(e["del"]), tuple(e["ins"]))
                if pair in set(_change_pairs(ops)):
                    entry.setdefault("global_changes", []).append(
                        " ".join(e["del"]) + " -> " + " ".join(e["ins"]))
        changes.append(entry)

    result = {
        "rulebook": "bme_mtf_equity",
        "from_version": (meta or {}).get("from_version"),
        "to_version": (meta or {}).get("to_version"),
        "source_hashes": (meta or {}).get("source_hashes", {}),
        "changed_articles": sorted(
            int(k) for k in keys if k != FINAL_KEY
            and statuses[k] in ("MODIFIED", "ADDED", "REMOVED")),
        "final_provision_changed": statuses.get(FINAL_KEY) not in
            (None, "UNCHANGED"),
        "global_change_events": global_change_events,
        "changes": changes,
    }
    return result


def human_report(result: dict, titles: dict[str, str] | None = None) -> str:
    titles = titles or {}
    lines = [
        "BME MTF Equity Rulebook",
        "",
        f"v{result['from_version']} → v{result['to_version']}",
        "",
    ]
    n = len(result["changed_articles"])
    lines.append(f"{n} article{'s' if n != 1 else ''} changed")
    if result.get("final_provision_changed"):
        lines.append("Final Provision changed")
    lines.append("")
    for c in result["changes"]:
        a = c["article"]
        title = titles.get(str(a), "")
        label = f"Article {a}" if a != "FINAL" else "Final Provision"
        extra = f"  {title}" if title else ""
        cls = f"  [{c['change_class']}]" if c.get("change_class") else ""
        lines.append(f"{label:<22}{c['status']}{cls}{extra}")
        for g in c.get("global_changes", []):
            lines.append(f"    global: {g}")
    return "\n".join(lines)
