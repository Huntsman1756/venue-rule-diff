"""G2 — parser robustness against the documented extraction artefacts."""

import os
import sys

import pymupdf
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.extract import (
    PageLine, article_number_of, clean_lines, extract, segment_pdf,
    _text_anchors, _merge_markers,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fx(name):
    return open(os.path.join(FIXTURES, name), encoding="utf-8").read()


# --- grammar ---------------------------------------------------------------

@pytest.mark.parametrize("line,num", [
    ("Artículo 3.- Órganos de gobierno", 3),
    ("Artículo 4- Régimen de responsabilidad", 4),      # no dot before hyphen
    ("Artículo 5 Consejo de Administración", 5),         # no punctuation
    ("Artículo 34. Difusión general", 34),               # dot only
    ("Artículo 1 - Objeto y ámbito", 1),                 # TOC form
    ("A rtículo 18.", 18),                               # split glyph
    ("Artí culo 36.", 36),                               # split glyph 2
    ("Artículo 16", 16),
])
def test_heading_variants(line, num):
    assert article_number_of(line) == num


@pytest.mark.parametrize("line", [
    "de acuerdo con el artículo 26 de este Reglamento",   # body reference
    "artículo 26 de este Reglamento",                     # line-start ref (lowercase)
    "el artículo 4 de este Reglamento y en las",
    "Artículos 16 y 18",
    "",
])
def test_heading_rejects_body_references(line):
    assert article_number_of(line) is None


def test_pairwise_split_heading():
    """'Artícu\\nlo 42.' must anchor as article 42."""
    lines = [PageLine(0, 100, 114, 71, "Artícu"),
             PageLine(0, 114, 128, 71, "lo 42.- Situaciones sobrevenidas")]
    anchors = _text_anchors(lines)
    assert len(anchors) == 1
    assert anchors[0].number == 42


# --- cleanup ---------------------------------------------------------------

def test_footer_and_pagenumber_cleanup():
    raw = [PageLine(0, 100, 114, 71, "Artículo 10.- Miembros"),
           PageLine(0, 200, 214, 71, "La negociación en el Mercado."),
           PageLine(0, 789, 801, 540, "6"),
           PageLine(0, 787, 801, 70,
                    "BME MTF Equity – Reglamento de funcionamiento"),
           PageLine(0, 800, 812, 70, "Aprobado el 30 de julio de 2020"),
           PageLine(0, 30, 45, 70,
                    "Classified as Internal / Clasificado como Interno"),
           PageLine(0, 300, 314, 71, "Podrán ser Miembros las entidades.")]
    kept = clean_lines(raw)
    texts = [l.text for l in kept]
    assert "6" not in texts
    assert not any("Reglamento de funcionamiento" == t.split("–")[-1].strip()
                   for t in texts)
    assert "La negociación en el Mercado." in texts
    assert "Podrán ser Miembros las entidades." in texts
    assert len(kept) == 3


def test_list_marker_merge():
    lines = [PageLine(0, 100, 114, 100, "a)"),
             PageLine(0, 100, 114, 128, "La Comisión deberá atender."),
             PageLine(0, 114, 128, 100, "b)"),
             PageLine(0, 114, 128, 128, "El plazo máximo.")]
    merged = _merge_markers(lines)
    texts = [l.text for l in merged]
    assert texts == ["a) La Comisión deberá atender.", "b) El plazo máximo."]


# --- synthetic end-to-end segmentation -------------------------------------

def _synth_pdf(articles_toc, body_blocks, tmp_path):
    """Build a synthetic rulebook PDF: TOC page + body pages."""
    doc = pymupdf.open()
    toc = doc.new_page()
    y = 80
    for n in articles_toc:
        toc.insert_text((71, y), f"Artículo {n} - Title {n}", fontsize=10)
        y += 14
    page = doc.new_page()
    y = 80
    for kind, payload in body_blocks:
        if kind == "pagebreak":
            page = doc.new_page()
            y = 80
            page.insert_text((540, 800), str(page.number + 1), fontsize=9)
            page.insert_text(
                (70, 800),
                "BME MTF Equity – Reglamento de funcionamiento", fontsize=8)
        else:
            for ln in payload.split("\n"):
                if ln:
                    page.insert_text((71, y), ln, fontsize=10)
                y += 14
    path = str(tmp_path / "synth.pdf")
    doc.save(path)
    doc.close()
    return path


def test_synth_segmentation(tmp_path):
    """A synthetic mini-rulebook with artefacts must segment cleanly."""
    arts = [1, 2, 3, 4, 5]
    body = [
        ("text", "Artículo 1.- Objeto\nTexto del artículo uno."),
        ("text", "Artículo 2.- Denominación\nTexto del artículo dos con "
                 "el artículo 26 de este Reglamento citado."),
        ("pagebreak", None),
        ("text", "Artículo 3- Órganos\nTexto tres."),
        ("text", "Artí culo 4.- Régimen\nTexto cuatro."),
        ("text", "Artícu\nlo 5.- Consejo\nTexto cinco."),
        ("text", "Disposición Final\nEl presente Reglamento entrará en vigor."),
    ]
    path = _synth_pdf(arts, body, tmp_path)
    ex = extract(path, ocr=False)
    assert sorted(ex.articles) == arts
    assert ex.final is not None
    # expected: only "missing article" warnings for numbers absent from the
    # synthetic mini-rulebook — no duplicate/split/merge complaints
    assert all(w.startswith("missing article") for w in ex.warnings)
    assert "artículo 26" in ex.articles[2].text          # ref kept as body
    assert "Reglamento de funcionamiento" not in ex.articles[3].text
    assert ex.articles[4].text.startswith("Texto cuatro")
    assert "vigor" in ex.final.text


def test_fixture_files_parse():
    for name in os.listdir(FIXTURES):
        txt = fx(name)
        assert txt.strip(), name
    # spot checks on grammar against fixture content
    assert article_number_of("Artículo 3.- Órganos de gobierno") == 3
    assert article_number_of("Artículo 4- Régimen de responsabilidad") == 4
    assert article_number_of("Artículo 5 Consejo de Administración de BMESN") == 5
