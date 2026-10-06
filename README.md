# venue-rule-diff

> **Article-level change detection for market rulebooks, with source
> provenance and validation against venue-published change logs.**
>
> Initial BME MTF Equity corpus: four historical rulebook versions, 47
> articles per version. The validator reproduced all 26 changes declared by
> BME for the July 2023 revision and identified one additional source-text
> correction not listed in the venue change log.

Scope of this release: **BME MTF Equity — Reglamento de funcionamiento**
(articles 1–47 plus the Final Provision). Not a general regulatory-document
platform.

## Provenance

A URL does not immutably identify a document — this corpus proves it:

```
v1 historical URL  → now serves a different document (current consolidated)
v2 URL             → now returns an HTML landing page
v4 URL             → now redirects to an unrelated document (venue misconfig)
Wayback captures   → truncated at 1 MiB / unusable
BME Documents API  → serves all four official versions today
```

Every version in `manifests/bme_mtf_equity.json` therefore records its
retrieval independently of its nominal `source_url`: discovery channel,
document identifier, asset URL, byte size and SHA-256 at fetch time, plus
corroborating sources where they exist (CNMV registry copy for v2; an
archived capture of the venue URL — byte-identical to the live file — and
the official English rulebook for v4).

| version | approved | retrieval | sha256 (first 12) |
|---|---|---|---|
| 1 | 2020-07-30 | BME Documents API, doc 70607 | `20d311457514` |
| 2 | 2022-07-22 | BME Documents API, doc 86766 + CNMV registry | `a24b65c467cc` |
| 3 | 2023-07-04 | BME Documents API, doc 94218 | `a0041368fcdb` |
| 4 | 2023-09-26 | BME Documents API, doc 95828 + archive copy | `6b02438429c5` |

The original PDFs are not redistributed (`data/raw/` is gitignored); public
output is limited to change excerpts and diffs.

## Validation

| Gate | Result |
|---|---|
| G0 source availability | **PASS** — 4/4 official versions recovered |
| G1 structural extraction | **PASS** — 47/47 + Final Provision × 4 |
| G2 parser robustness | **PASS** — real artefacts covered by fixtures |
| G3 v1→v2 oracle | **PASS** — detected `{16, 18}` exactly |
| G4a declared recall | **PASS** — 26/26 declared changes detected |
| G4b undeclared control | **PASS** — 1 extra (art. 14, verified), 0 unexplained |
| G5 v3→v4 transversal | **PASS** — 8 articles + 1 shared `BME Scale → BME Scaleup` event |
| G6 determinism | **PASS** — byte-identical under the declared toolchain |

**G4 discovered that the BME change log is not exhaustive.** Article 14
differs between v2 and v3 source bytes — `"Miembro de la Bolsa. y de las
que"` → `"Miembro de la Bolsa y de las que"` — a real punctuation
correction the venue never declared. It is surfaced (classified
`formatting`) rather than suppressed: the product compares real documents,
not change logs.

## Usage

```bash
python -m src.cli validate 3        # G1 structural gate on version 3
python -m src.cli compare 1 2       # machine-readable diff v1 -> v2 (JSON)
python -m src.cli report 3 4        # human-readable report
python -m src.cli site              # generate site/ HTML for v1->v2->v3->v4
python -m pytest tests/             # parser/normalization unit tests + gates
```

`tests/test_gates.py` skips when the official PDFs are absent from `data/raw/`.

## Extraction notes

* The PDFs' embedded fonts have no usable ToUnicode cmap; extraction uses
  `TEXT_CID_FOR_UNKNOWN_UNICODE` (the CIDs are the real Unicode points).
* The July 2022 version renders every heading as bitmap strips plus a buggy
  invisible text overlay. Heading anchors are recovered by OCR of the strip
  regions — **OCR recovers structure, never fabricates normative text** —
  with strict 1–47 sequence validation.
* Determinism means *deterministic under the declared extraction
  toolchain* (PyMuPDF 1.28.2, Tesseract 5.4.0, `eng` traineddata, 300 dpi,
  `--psm 6`), recorded in the manifest — not universal determinism across
  OCR/renderer versions.
* Article detection is anchored to line starts and tolerates the documented
  heading variants (`Artículo N.-`, `Artículo N-`, `Artículo N Título`,
  split-glyph `A rtículo 18.`/`Artí culo 36.`, two-line `Artícu\nlo 42.`).
  Body references such as `artículo 26 de este Reglamento` are rejected by
  the capital-A anchor.
* TOC vs body: the TOC lists articles 1–47 once, the body repeats them; the
  body starts at the second article-1 anchor. TOC/body mismatches produce
  validation warnings, never a regulatory change.
* Section (Título) headers are excluded from article content; in v2 they
  exist only as images and symmetric treatment matters more than section
  names.

## Diff semantics

* Alignment: `article_number -> article_number`, no fuzzy matching.
* Status per unit: `UNCHANGED | MODIFIED | ADDED | REMOVED`.
* MODIFIED units carry a deterministic word-level diff plus a
  `change_class` (`substantive | terminology | cross_reference |
  formatting | unknown`) that never alters the raw diff.
* `global_change_events` groups identical token substitutions reused across
  articles, preserving both levels of truth (per-article diffs plus the
  shared semantic cause).

## Requirements

* Python 3.11+ with `pymupdf` (extraction), `pytest` (tests).
* Tesseract OCR (only for the v2 heading strips; `TESSERACT_CMD` in
  `src/extract.py` if not on PATH).
