"""Extraction of the BME MTF Equity rulebook PDFs into article-level segments.

Pipeline per document:

1. Per-page line extraction with positions (pymupdf ``dict`` mode).  The
   ``TEXT_CID_FOR_UNKNOWN_UNICODE`` flag is required: the embedded fonts in
   these PDFs have no usable ToUnicode cmap but use Unicode code points
   directly as CIDs.
2. Heading anchors from two detectors:
     a. text-layer article headings (tolerant to spaces injected inside the
        word "Artículo" and to headings split over two lines);
     b. heading image strips resolved via OCR (the July 2022 version renders
        every heading as a bitmap plus a buggy invisible text overlay).
3. Body/TOC separation: the TOC lists articles 1..47 once, then the body
   repeats them; the body starts at the second article-1 anchor.
4. Segmentation into articles 1..47 plus the Final Provision.

Design decisions:

* Article *content* is the body text only.  The heading line itself is not
  part of the diff unit (its number is the alignment key; titles are kept
  from the TOC for display).
* Section ("Título") headers are excluded from article content: in v2 they
  exist only as images, and symmetric treatment across versions is more
  important than capturing section names.  A renamed section header would
  therefore not appear as an article change.
* OCR is used only where the text layer lacks headings (v2).  Its output is
  used for anchor labels only, never for article body text.

Determinism (gate G6) means byte-identical output under the *declared*
extraction toolchain — see ``TOOLCHAIN`` and
``manifests/bme_mtf_equity.json#extraction_toolchain`` — not universal
determinism across OCR/renderer versions.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass, field

import pymupdf

TEXT_FLAGS = pymupdf.TEXTFLAGS_DICT | pymupdf.TEXT_CID_FOR_UNKNOWN_UNICODE

TESSERACT_CMD = "tesseract"
OCR_DPI = 300
OCR_PSM = "6"
OCR_LANG = "eng"

# Declared extraction toolchain (mirrors manifests/bme_mtf_equity.json).
TOOLCHAIN = {
    "pdf_renderer": "PyMuPDF",
    "pdf_renderer_version": "1.28.2",
    "ocr_engine": "tesseract",
    "ocr_engine_version": "5.4.0.20240606",
    "ocr_language_data": OCR_LANG,
    "ocr_render_dpi": OCR_DPI,
    "ocr_args": ["--psm", OCR_PSM],
}


def toolchain_info() -> dict:
    """Report the toolchain actually present vs. the declared one."""
    import shutil
    actual = {"pymupdf": pymupdf.__version__, "tesseract": None,
              "tesseract_path": shutil.which(TESSERACT_CMD)}
    if actual["tesseract_path"]:
        try:
            r = subprocess.run([TESSERACT_CMD, "--version"],
                               capture_output=True, text=True, timeout=15)
            actual["tesseract"] = r.stdout.splitlines()[0].strip() \
                if r.stdout else None
        except Exception:
            pass
    return {"declared": TOOLCHAIN, "actual": actual}

EXPECTED_ARTICLES = list(range(1, 48))

FOOTER_PATTERNS = [
    re.compile(r"^BME MTF Equity\s*[–—\-]\s*Reglamento de funcionamiento\s*$"),
    re.compile(r"^Aprobado el \d{1,2} de \w+ de \d{4}\s*$"),
    re.compile(r"^Classified as Internal\s*/\s*Clasificado como Interno\s*$"),
]

BOILERPLATE_START = re.compile(r"^Este material ha sido preparado por")

DISPOSICION_RE = re.compile(r"^Disposici\w*\s+Final\s*$", re.I)

TITULO_NUM_RE = re.compile(r"^T[IÍ]TULO\s+([IVX]+)", re.I)

_PAGENUM_RE = re.compile(r"^\d{1,3}\s*$")


def _compact(s: str) -> str:
    return s.replace(" ", "").replace(" ", "")


_ARTICULO_COMPACT_RE = re.compile(r"^Art.culo\.?-?(\d{1,2})(?!\d)")


def article_number_of(line: str) -> int | None:
    """Return the article number if *line* is an article heading.

    Tolerates spaces injected inside the word "Artículo" (page-boundary
    artefact: "Artí culo 36.", "A rtículo 18.").  Case-sensitive on the
    capital A so that body references such as "artículo 26 de este
    Reglamento" are rejected.
    """
    m = _ARTICULO_COMPACT_RE.match(_compact(line.strip()))
    return int(m.group(1)) if m else None


_HEADING_RE = re.compile(
    r"^\s*A\s*rt.culo\s*\.?\s*-?\s*(\d{1,2})\s*[.\-–—]?\s*(.*)$")


def heading_parts(line: str) -> tuple[int, str] | None:
    """Return (number, title-rest) for an article heading line."""
    m = _HEADING_RE.match(line.strip())
    if not m:
        return None
    return int(m.group(1)), m.group(2).strip()


def _deaccent(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def _is_articulo_fragment(line: str) -> bool:
    """True if the line is a prefix fragment of the word Artículo."""
    c = _deaccent(_compact(line.strip()).lower())
    return 0 < len(c) <= 8 and ("articulo".startswith(c) or c == "artculo")


def _is_titulo_line(line: str) -> bool:
    return bool(TITULO_NUM_RE.match(line.strip()))


def _is_allcaps_heading(line: str) -> bool:
    s = line.strip()
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


# ---------------------------------------------------------------------------
# raw page model
# ---------------------------------------------------------------------------

@dataclass
class PageLine:
    page: int
    y0: float
    y1: float
    x0: float
    text: str


@dataclass
class Anchor:
    page: int
    y0: float
    y1: float
    number: int | None          # article number; None while unresolved
    kind: str                    # "article" | "titulo" | "final"
    label: str = ""
    source: str = "text"         # "text" | "ocr" | "inferred"


def extract_lines(pdf: pymupdf.Document) -> list[PageLine]:
    """All text lines of the document in reading order."""
    lines: list[PageLine] = []
    for pi in range(pdf.page_count):
        page_lines: list[PageLine] = []
        for block in pdf[pi].get_text("dict", flags=TEXT_FLAGS)["blocks"]:
            for ln in block.get("lines", []):
                text = "".join(sp["text"] for sp in ln["spans"])
                text = unicodedata.normalize("NFC", text).rstrip()
                if not text.strip():
                    continue
                x0, y0, x1, y1 = ln["bbox"]
                page_lines.append(PageLine(pi, y0, y1, x0, text.strip()))
        page_lines.sort(key=lambda l: (round(l.y0, 1), l.x0))
        lines.extend(_merge_markers(page_lines))
    return lines


_MARKER_RE = re.compile(r"^([a-z]\)|[a-z]\.|\d{1,2}[.)]|[ivx]+\)|[-–])$")


def _merge_markers(page_lines: list[PageLine]) -> list[PageLine]:
    """Merge standalone list markers into the text line they precede.

    The sources typeset list markers (``a)``, ``1.``) as separate spans at
    the same y as their text but at a smaller x; naïve y-ordering then
    drops the marker mid-sentence.  A marker line within ~4 pt of a line
    starting further right is prepended to it.
    """
    result: list[PageLine] = []
    for i, l in enumerate(page_lines):
        if _MARKER_RE.match(l.text) and len(l.text) <= 3:
            best = None
            for j, cand in enumerate(page_lines):
                if j == i or cand is l:
                    continue
                if abs(cand.y0 - l.y0) < 4 and cand.x0 > l.x0:
                    if best is None or abs(cand.y0 - l.y0) < abs(best.y0 - l.y0):
                        best = cand
            if best is not None:
                best.text = l.text + " " + best.text
                continue
        result.append(l)
    return result


def clean_lines(lines: list[PageLine]) -> list[PageLine]:
    """Drop furniture lines and everything from the BME legal boilerplate
    that trails the Aviso-published versions."""
    out: list[PageLine] = []
    for i, l in enumerate(lines):
        t = l.text.strip()
        if BOILERPLATE_START.match(t):
            break
        if any(p.match(t) for p in FOOTER_PATTERNS):
            continue
        if _PAGENUM_RE.match(t):
            # keep a bare number that continues a split heading
            # ("Artículo \n5"); otherwise it is a page number
            prev = out[-1].text if out else ""
            if _is_articulo_fragment(prev):
                out.append(l)
            continue
        out.append(l)
    return out


# ---------------------------------------------------------------------------
# anchors
# ---------------------------------------------------------------------------

def _text_anchors(lines: list[PageLine]) -> list[Anchor]:
    anchors: list[Anchor] = []
    n = len(lines)
    for i, l in enumerate(lines):
        num = article_number_of(l.text)
        if num is not None:
            anchors.append(Anchor(l.page, l.y0, l.y1, num, "article",
                                  label=l.text, source="text"))
            continue
        # heading split over two physical lines ("Artícu\nlo 42.",
        # "Artículo\n5.-")
        if _is_articulo_fragment(l.text) and i + 1 < n \
                and lines[i + 1].page == l.page:
            joined = l.text + " " + lines[i + 1].text
            num = article_number_of(joined)
            if num is not None:
                anchors.append(Anchor(l.page, l.y0, lines[i + 1].y1, num,
                                      "article", label=joined, source="text"))
                continue
        if DISPOSICION_RE.match(l.text):
            anchors.append(Anchor(l.page, l.y0, l.y1, None, "final",
                                  label=l.text, source="text"))
    return anchors


def _image_rows(pdf: pymupdf.Document, page_index: int) -> list[tuple[float, float]]:
    """Heading rows rendered as image strips.

    In the July 2022 version every heading is a cluster of small per-glyph
    image strips sharing a common y-range.  Strips are clustered into rows;
    a row qualifies when its merged extent starts at the left margin
    (article headings) or is roughly centred (Título / Disposición Final).
    Rows closer than ~6 pt vertically are merged so that a two-line heading
    counts once.
    """
    strips: list[tuple[float, float, float, float]] = []
    for img in pdf[page_index].get_image_info(xrefs=True):
        x0, y0, x1, y1 = img["bbox"]
        if 60 < y0 < 770 and (y1 - y0) < 40 and (x1 - x0) > 3:
            strips.append((x0, y0, x1, y1))
    strips.sort(key=lambda s: (s[1], s[0]))

    # cluster strips sharing a y-range into rows
    rows: list[list[float]] = []  # [x0, y0, x1, y1]
    for x0, y0, x1, y1 in strips:
        if rows and y0 - rows[-1][3] < 4:
            r = rows[-1]
            r[0] = min(r[0], x0); r[1] = min(r[1], y0)
            r[2] = max(r[2], x1); r[3] = max(r[3], y1)
        else:
            rows.append([x0, y0, x1, y1])

    kept = [r for r in rows
            if (r[0] < 95 and r[2] - r[0] > 55)          # left-margin heading
            or (150 < r[0] < 450 and r[2] - r[0] > 40)]  # centred heading

    merged: list[list[float]] = []
    for r in kept:
        if merged and r[1] - merged[-1][3] < 6:
            m = merged[-1]
            m[0] = min(m[0], r[0]); m[1] = min(m[1], r[1])
            m[2] = max(m[2], r[2]); m[3] = max(m[3], r[3])
        else:
            merged.append(r)
    return [(r[1], r[3]) for r in merged]


def _ocr_strip(pdf: pymupdf.Document, page_index: int,
               y0: float, y1: float) -> str:
    pix = pdf[page_index].get_pixmap(
        clip=pymupdf.Rect(55, y0 - 6, 590, y1 + 6), dpi=OCR_DPI)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        pix.save(path)
        r = subprocess.run(
            [TESSERACT_CMD, path, "-", "--psm", OCR_PSM, "-l", OCR_LANG],
            capture_output=True, text=True, timeout=60)
        return " ".join(r.stdout.split())
    finally:
        import os
        try:
            os.unlink(path)
        except OSError:
            pass


def _image_anchors(pdf: pymupdf.Document, first_body_page: int,
                   ocr: bool) -> list[Anchor]:
    anchors: list[Anchor] = []
    for pi in range(first_body_page, pdf.page_count):
        for y0, y1 in _image_rows(pdf, pi):
            label = _ocr_strip(pdf, pi, y0, y1) if ocr else ""
            num = article_number_of(label) if label else None
            if num is not None:
                anchors.append(Anchor(pi, y0, y1, num, "article",
                                      label=label, source="ocr"))
            elif label and DISPOSICION_RE.match(label):
                anchors.append(Anchor(pi, y0, y1, None, "final",
                                      label=label, source="ocr"))
            elif label and (_is_titulo_line(label) or _is_allcaps_heading(label)):
                anchors.append(Anchor(pi, y0, y1, None, "titulo",
                                      label=label, source="ocr"))
            # rows that OCR to nothing or to a lowercase fragment are
            # rendering artefacts (e.g. second line of a wrapped title)
            # and carry no structural meaning
    return anchors


# ---------------------------------------------------------------------------
# segmentation
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    key: str                     # "1".."47" or "FINAL"
    title: str
    text: str
    source: str = "text"


@dataclass
class Extraction:
    articles: dict[int, Segment]
    final: Segment | None
    toc: list[tuple[int, str]]
    warnings: list[str]
    page_count: int
    used_ocr: bool = False


def _join_lines(lines: list[str]) -> str:
    paras: list[str] = []
    cur: list[str] = []
    for ln in lines:
        if ln == "":
            if cur:
                paras.append(" ".join(cur))
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def _body_start(anchors: list[Anchor]) -> int:
    ones = [i for i, a in enumerate(anchors)
            if a.kind == "article" and a.number == 1]
    if len(ones) >= 2:
        return ones[1]
    return ones[0] if ones else 0


def _resolve_missing(anchors: list[Anchor], warnings: list[str]) -> None:
    prev = 0
    for a in anchors:
        if a.kind == "article":
            if a.number is None:
                a.number = prev + 1
                a.source = "inferred"
                warnings.append(
                    f"article {a.number} heading inferred by sequence "
                    f"(p{a.page} y{a.y0:.0f})")
            prev = a.number


def segment_pdf(pdf: pymupdf.Document, ocr: bool = True) -> Extraction:
    warnings: list[str] = []

    raw_lines = extract_lines(pdf)
    text_anchors = _text_anchors(raw_lines)
    body_idx_text = _body_start(text_anchors)
    first_body_page = text_anchors[body_idx_text].page if text_anchors else 0

    img_anchors = _image_anchors(pdf, first_body_page, ocr)

    anchors = sorted(text_anchors + img_anchors,
                     key=lambda a: (a.page, a.y0))

    # dedupe anchors covering the same heading (text overlay + image row)
    deduped: list[Anchor] = []
    for a in anchors:
        prev = deduped[-1] if deduped else None
        if prev and a.page == prev.page and a.y0 - prev.y0 < 6 \
                and a.kind == prev.kind:
            if prev.number is None and a.number is not None:
                prev.number, prev.label, prev.source = a.number, a.label, a.source
            continue
        # an unlabelled image row directly above a text article anchor is
        # the same heading rendered twice
        if prev and a.kind == "article" and prev.kind != "article" \
                and prev.number is None and a.page == prev.page \
                and a.y0 - prev.y0 < 6:
            deduped[-1] = a
            continue
        deduped.append(a)
    anchors = deduped

    body_idx = _body_start(anchors)
    toc_anchors = [a for a in anchors[:body_idx] if a.kind == "article"]
    body_anchors = anchors[body_idx:]

    _resolve_missing(body_anchors, warnings)

    toc_titles = {a.number: (heading_parts(a.label) or (a.number, ""))[1]
                  for a in toc_anchors if a.number is not None}

    # duplicate heading detection before segments overwrite each other
    seen: dict[int, int] = {}
    for a in body_anchors:
        if a.kind == "article" and a.number is not None:
            seen[a.number] = seen.get(a.number, 0) + 1
    for n, c in seen.items():
        if c > 1:
            warnings.append(f"duplicate heading for article {n} ({c}x)")

    lines = clean_lines(raw_lines)

    # merged event stream: anchors and content lines in reading order
    events: list[tuple[int, float, int, object]] = []
    for l in lines:
        if l.page < first_body_page:
            continue
        events.append((l.page, l.y0, 1, l))
    for a in body_anchors:
        events.append((a.page, a.y0, 0, a))
    events.sort(key=lambda e: (e[0], e[1], e[2]))

    articles: dict[int, Segment] = {}
    final: Segment | None = None
    current_key: str | None = None
    current_title = ""
    current_source = "text"
    buf: list[str] = []
    in_titulo = False          # skipping section-header lines
    expect_continuation = False  # next line may be a wrapped heading title

    def covered_by_anchor(l: PageLine) -> Anchor | None:
        for a in body_anchors:
            if l.page == a.page and a.y0 - 1 <= l.y0 <= a.y1 - 1:
                return a
        return None

    def flush():
        nonlocal buf, current_key, final
        if current_key is None:
            buf = []
            return
        text = _join_lines(buf)
        if current_key == "FINAL":
            final = Segment("FINAL", "Disposición Final", text, current_source)
        else:
            articles[int(current_key)] = Segment(
                current_key, current_title, text, current_source)
        buf = []

    for page, y, kind, obj in events:
        if kind == 0:  # anchor
            a: Anchor = obj
            if a.kind == "article":
                flush()
                current_key = str(a.number)
                current_title = toc_titles.get(
                    a.number,
                    (heading_parts(a.label) or (a.number, ""))[1])
                current_source = a.source
                in_titulo = False
                expect_continuation = True
            elif a.kind == "final":
                flush()
                current_key = "FINAL"
                current_title = "Disposición Final"
                current_source = a.source
                in_titulo = False
                expect_continuation = True
            else:  # titulo
                in_titulo = True
                expect_continuation = False
            continue

        l: PageLine = obj
        if covered_by_anchor(l):
            continue
        if _is_titulo_line(l.text):
            in_titulo = True
            continue
        if in_titulo and _is_allcaps_heading(l.text):
            continue
        in_titulo = False
        if current_key is None:
            expect_continuation = False
            continue
        if expect_continuation:
            expect_continuation = False
            if l.text and l.text[0].islower():
                # lowercase-starting line directly below a heading is a
                # wrapped title fragment, not body text
                continue
        buf.append(l.text)

    flush()

    nums = sorted(articles)
    for n in EXPECTED_ARTICLES:
        if n not in articles:
            warnings.append(f"missing article {n}")
    if final is None:
        warnings.append("final provision not found")

    return Extraction(articles=articles, final=final, toc=list(toc_titles.items()),
                      warnings=warnings, page_count=pdf.page_count,
                      used_ocr=any(a.source in ("ocr", "inferred")
                                   for a in body_anchors))


def extract(path: str, ocr: bool = True) -> Extraction:
    doc = pymupdf.open(path)
    try:
        return segment_pdf(doc, ocr=ocr)
    finally:
        doc.close()
