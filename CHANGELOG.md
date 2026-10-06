# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — 2026-10-06

Initial release. BME MTF Equity only (articles 1–47 + Final Provision).

### Added

- Provenance manifests for all four official versions (2020, 2022, 2023-07,
  2023-09): retrieval channel, document ID, byte size, SHA-256, verification
  status, corroborating sources.
- Extraction pipeline: CID-aware text layer reading, footer/page-number
  cleanup, tolerant article-heading grammar, list-marker merge, TOC/body
  separation, OCR recovery of image-rendered headings (anchors only).
- Article-aligned diff engine: `UNCHANGED|MODIFIED|ADDED|REMOVED` status,
  word-level diffs, change classification, `global_change_events` for
  transversal substitutions.
- CLI: `fetch`, `validate`, `compare` (JSON), `report`, `site`, `toolchain`.
- Minimal static HTML output under `site/` (change excerpts only).
- Validation gates G0–G6, split as G4a (declared recall, 26/26) and G4b
  (undeclared-change control, article 14 verified, 0 unexplained).

### Notable findings

- 3 of 4 originally-recorded source URLs no longer serve the expected
  documents; all versions recovered via the venue's own documents API.
- Article 14 carries a real punctuation correction in the v2→v3 source
  bytes that the venue's change log does not declare.

[0.1.0]: https://github.com/USER/venue-rule-diff/releases/tag/v0.1.0
