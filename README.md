# venue-rule-diff

Detects changes between successive official versions of a market rulebook and
identifies exactly which regulatory articles changed and what text was added
or removed.

Scope of this release: **BME MTF Equity — Reglamento de funcionamiento**
(articles 1–47 plus the Final Provision). Not a general regulatory-document
platform.

> Designed for validation against the venue's published historical change log.

## Provenance

All four official versions were retrieved from the venue's own document
service and are recorded in `manifests/bme_mtf_equity.json` with SHA-256,
retrieval timestamps, document types, and verification status. The original
PDFs are not redistributed (`data/raw/` is gitignored); public output is
limited to change excerpts and diffs.

| version | approved | source | sha256 (first 12) |
|---|---|---|---|
| 1 | 2020-07-30 | BME Aviso 2020-09-03 | `20d311457514` |
| 2 | 2022-07-22 | BME Aviso 2022-07-22 | `a24b65c467cc` |
| 3 | 2023-07-04 | BME Aviso 2023-07-07 | `a0041368fcdb` |
| 4 | 2023-09-26 | BME Aviso 2023-10-03 | `6b02438429c5` |

Two URLs originally listed in the project spec no longer serve the expected
documents (the 2020 `circulares` URL now serves the current consolidated
rulebook; the `bmegrowth.es` v4 URL redirects to an unrelated Circular).
The canonical sources are recorded per-version in the manifest.

## Usage

```bash
python -m src.cli validate 3        # G1 structural gate on version 3
python -m src.cli compare 1 2       # machine-readable diff v1 -> v2 (JSON)
python -m src.cli report 3 4        # human-readable report
python -m src.cli site              # generate site/ HTML for v1->v2->v3->v4
```

Tests:

```bash
python -m pytest tests/             # parser/normalization unit tests + gates
```

`tests/test_gates.py` skips when the official PDFs are absent from `data/raw/`.

## Extraction notes

* The PDFs' embedded fonts have no usable ToUnicode cmap; extraction uses
  `TEXT_CID_FOR_UNKNOWN_UNICODE` (the CIDs are the real Unicode points).
* The July 2022 version renders every heading as bitmap strips plus a buggy
  invisible text overlay. Heading anchors are recovered by OCR of the strip
  regions (Tesseract, deterministic per binary version) with sequence
  inference as a safety net; OCR output is used for anchors only, never for
  article body text.
* Article detection is anchored to line starts and tolerates the documented
  heading variants (`Artículo N.-`, `Artículo N-`, `Artículo N Título`,
  split-glyph headings like `A rtículo 18.`/`Artí culo 36.` and the
  two-line `Artícu\nlo 42.`). Body references such as
  `artículo 26 de este Reglamento` are rejected by the capital-A anchor.
* TOC vs body: the TOC lists articles 1–47 once, the body repeats them; the
  body starts at the second article-1 anchor. TOC/body mismatches produce
  validation warnings, never a regulatory change.
* Section (Título) headers are excluded from article content; in v2 they
  exist only as images and symmetric treatment matters more than the section
  names.
* A punctuation-only correction detected between v2 and v3 (article 14,
  `Bolsa. y` → `Bolsa y`, present in the source bytes of both versions) is
  real but undeclared by the venue's change log; it is surfaced and
  classified `formatting`.

## Diff semantics

* Alignment: `article_number -> article_number`, no fuzzy matching.
* Status per unit: `UNCHANGED | MODIFIED | ADDED | REMOVED`.
* MODIFIED units carry a deterministic word-level diff plus a
  `change_class` (`substantive | terminology | cross_reference |
  formatting | unknown`) that never alters the raw diff.
* `global_change_events` groups identical token substitutions reused across
  articles (e.g. `BME Scale -> BME Scaleup`), preserving both levels of
  truth required by G5.

## Requirements

* Python 3.11+ with `pymupdf` (extraction), `pytest` (tests).
* Tesseract OCR (only for the v2 heading strips; `TESSERACT_CMD` in
  `src/extract.py` if not on PATH).
