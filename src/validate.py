"""Validation gates for extracted rulebook segmentations.

G1 — structural extraction: articles 1..47 each exactly once, plus the
     Final Provision exactly once; no missing, duplicate, merged or split
     articles.
TOC  — integrity check: TOC article set must match the body article set;
       a discrepancy is a warning, never a regulatory change.
"""

from __future__ import annotations

from .extract import Extraction, EXPECTED_ARTICLES


def validate_extraction(ex: Extraction) -> dict:
    """Run the G1 structural gate plus the TOC integrity check."""
    warnings: list[str] = list(ex.warnings)

    nums = sorted(ex.articles)
    missing = [n for n in EXPECTED_ARTICLES if n not in ex.articles]
    extra = [n for n in nums if n not in EXPECTED_ARTICLES]

    if missing:
        warnings.append(f"missing articles: {missing}")
    if extra:
        warnings.append(f"unexpected article numbers: {extra}")
    if ex.final is None:
        warnings.append("final provision missing")

    # TOC integrity: warning only, never a change
    toc_nums = sorted(n for n, _ in ex.toc)
    if toc_nums and toc_nums != nums:
        only_toc = sorted(set(toc_nums) - set(nums))
        only_body = sorted(set(nums) - set(toc_nums))
        warnings.append(
            f"TOC/body mismatch (toc_only={only_toc}, body_only={only_body})")
    if len(toc_nums) != len(set(toc_nums)):
        warnings.append("duplicate article entries in TOC")

    g1 = (not missing and not extra and ex.final is not None
          and len(nums) == 47)

    return {
        "g1_pass": g1,
        "articles_extracted": len(nums),
        "articles_expected": 47,
        "final_provision": ex.final is not None,
        "warnings": warnings,
    }
