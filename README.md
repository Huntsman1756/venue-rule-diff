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

## Install

```bash
pip install -e .[dev]
```

## Usage

```bash
venue-rule-diff fetch            # retrieve official sources to data/raw/
venue-rule-diff validate 3       # G1 structural gate on version 3
venue-rule-diff compare 1 2      # machine-readable diff v1 -> v2 (JSON)
venue-rule-diff report 3 4       # human-readable report
venue-rule-diff site             # generate site/ for v1->v2->v3->v4
venue-rule-diff toolchain        # declared vs actual extraction toolchain
```

```bash
pytest                           # unit tests + validation gates
```

> CI validates the offline test suite. Real-corpus gates require the
> official PDFs retrieved with `venue-rule-diff fetch` and are therefore
> not executed in GitHub-hosted CI (`live-source` runs them on demand).

## Highlights

* **Provenance first.** A URL does not immutably identify a document — 3 of
  4 originally-recorded URLs now serve different content. Every version is
  anchored by discovery channel, document ID, bytes, and SHA-256, with
  corroborating sources recorded separately.
  → [docs/provenance.md](docs/provenance.md)
* **Hostile-PDF extraction.** Broken font ToUnicode maps recovered via CID
  interpretation; the July 2022 version's image-rendered headings recovered
  by OCR — for structural anchors only, never for normative text.
  → [docs/extraction.md](docs/extraction.md)
* **Validated against the venue's own change log.** All declared changes
  reproduced; one verified undeclared source-text correction surfaced —
  evidence that the BME change log is not exhaustive.
  → [docs/gates.md](docs/gates.md)

## Layout

```
venue_rule_diff/     package: download, extract, normalize, validate,
                     diff, sitegen, cli
manifests/           provenance (sources, hashes, toolchain, verification)
tests/               unit tests + fixtures + validation gates
docs/                extraction, provenance and gate documentation
site/                generated HTML output (change excerpts only)
data/raw/            official PDFs — gitignored, never committed
```

## Requirements

Python 3.11+, `pymupdf`, `pytest` (dev). Tesseract OCR is required only for
the July 2022 version's image-rendered heading strips.

## License

MIT — see [LICENSE](LICENSE). The BME rulebook documents themselves are not
part of this repository and are not covered by this license.
