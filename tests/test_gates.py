"""Validation gates G1–G6 against the real source corpus.

Requires the official PDFs in data/raw/ (gitignored).  Skipped when absent.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.diff import diff_extractions
from src.extract import extract
from src.validate import validate_extraction
from src.normalize import normalize_text

RAW = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
VERSIONS = ["v1", "v2", "v3", "v4"]

pytestmark = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(RAW, f"bme_mtf_equity_{v}.pdf"))
            for v in VERSIONS),
    reason="official source PDFs not present in data/raw")


@pytest.fixture(scope="module")
def extractions():
    return {v: extract(os.path.join(RAW, f"bme_mtf_equity_{v}.pdf"))
            for v in VERSIONS}


# --- G1: structural extraction ----------------------------------------------

@pytest.mark.parametrize("v", VERSIONS)
def test_g1_structure(extractions, v):
    res = validate_extraction(extractions[v])
    assert res["g1_pass"], res["warnings"]
    assert res["articles_extracted"] == 47
    assert res["final_provision"]


# --- G3: v1 -> v2 oracle -----------------------------------------------------

def test_g3_v1_v2(extractions):
    res = diff_extractions(extractions["v1"], extractions["v2"], {})
    assert res["changed_articles"] == [16, 18]


# --- G4: v2 -> v3 oracle -----------------------------------------------------
#
# Split into two assertions, stronger than the original equality gate:
#
#   G4a — declared-change recall:   declared ⊆ detected   → 26/26
#   G4b — undeclared-change control: detected - declared
#         == verified_exceptions    → {14}, all verified; 0 unexplained
#
# Article 14 is a genuine source-text correction present in the v2 bytes
# ("Miembro de la Bolsa. y de las que" → v3 "Miembro de la Bolsa y de las
# que") that the venue's change log does not declare.  It is surfaced
# deliberately: the product compares real documents, and G4 thereby
# demonstrates that the BME change log is not exhaustive.

EXPECTED_V2_V3 = {1, 4, 5, 6, 7, 10, 11, 13, 15, 16, 17, 18, 19, 20, 21, 22,
                  24, 25, 26, 29, 31, 32, 35, 36, 37, 40}

VERIFIED_UNDECLARED = {
    14: {
        "v2": "Miembro de la Bolsa. y de las que",
        "v3": "Miembro de la Bolsa y de las que",
        "change_class": "formatting",
        "status": "VERIFIED_UNDECLARED_CHANGE",
    }
}


def test_g4a_declared_recall(extractions):
    """G4a: every article the venue declared changed must be detected."""
    res = diff_extractions(extractions["v2"], extractions["v3"], {})
    detected = set(res["changed_articles"])
    assert EXPECTED_V2_V3 <= detected


def test_g4b_undeclared_control(extractions):
    """G4b: extras must be exactly the verified exceptions; none unexplained."""
    res = diff_extractions(extractions["v2"], extractions["v3"], {})
    detected = set(res["changed_articles"])
    extras = detected - EXPECTED_V2_V3
    assert extras == set(VERIFIED_UNDECLARED), \
        f"unexplained extras: {extras - set(VERIFIED_UNDECLARED)}"
    for c in res["changes"]:
        if c["article"] in VERIFIED_UNDECLARED:
            toks = [t for op in c["diff"]
                    for t in op.get("del", []) + op.get("ins", [])]
            assert all(not t.isalnum() for t in toks), c["diff"]
            assert c["change_class"] == "formatting"
    # the 21 declared-unchanged articles must all be detected unchanged
    unchanged = set(range(1, 48)) - detected
    declared_unchanged = set(range(1, 48)) - EXPECTED_V2_V3 - extras
    assert unchanged == declared_unchanged


# --- G5: v3 -> v4 transversal terminology change -----------------------------

def test_g5_v3_v4_terminology(extractions):
    res = diff_extractions(extractions["v3"], extractions["v4"], {})
    # every article containing "BME Scale" in v3 must be detected
    with_scale = {n for n, s in extractions["v3"].articles.items()
                  if "BME Scale" in s.text}
    assert set(res["changed_articles"]) == with_scale
    # article-level changes are preserved AND the shared cause is surfaced
    events = [(" ".join(e["del"]), " ".join(e["ins"]))
              for e in res["global_change_events"]]
    assert ("BME Scale", "BME Scaleup") in events or ("Scale", "Scaleup") in events
    for c in res["changes"]:
        assert c["change_class"] == "terminology"
        assert c["diff"], "raw diff must be preserved alongside classification"


# --- G6: determinism under the declared toolchain -----------------------------

def test_g6_determinism():
    a1 = extract(os.path.join(RAW, "bme_mtf_equity_v2.pdf"))
    a2 = extract(os.path.join(RAW, "bme_mtf_equity_v2.pdf"))
    for n in range(1, 48):
        assert normalize_text(a1.articles[n].text) == \
            normalize_text(a2.articles[n].text)
    v1 = extract(os.path.join(RAW, "bme_mtf_equity_v1.pdf"))
    r1 = diff_extractions(v1, a1, {})
    r2 = diff_extractions(v1, a2, {})
    assert r1 == r2
