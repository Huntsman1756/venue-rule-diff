"""Normalization and determinism tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.normalize import normalize_text, tokenize

NBSP = " "
PUA_DASH = ""
MINUS = "−"


def test_whitespace_and_nbsp():
    t = "El  Mercado" + NBSP + "está   dirigido.\n\n\nOtro párrafo.  "
    assert normalize_text(t) == "El Mercado está dirigido.\n\nOtro párrafo."


def test_glyph_alias():
    assert normalize_text("a " + PUA_DASH + " b") == "a " + MINUS + " b"


def test_tokenize():
    assert tokenize("BME Scale, ahora.") == \
        ["BME", "Scale", ",", "ahora", "."]


def test_deterministic():
    t = "  Texto con  espacios\n\n y saltos " + PUA_DASH + " de línea.  "
    assert normalize_text(t) == normalize_text(t)


def test_normalize_is_idempotent():
    t = "Texto\n\n\ncon  ruido"
    assert normalize_text(normalize_text(t)) == normalize_text(t)
