# Provenance model

## Finding: a URL does not immutably identify a document

Of the four source URLs originally recorded for this corpus, three now
serve different content than the versions they once carried:

| version | nominal URL | what it serves today |
|---|---|---|
| 1 | `circulares/2020/Reglamento_BME_MTF_Equity.pdf` | the **current consolidated** rulebook |
| 2 | `circulares/2022/...julio_2022.pdf` | an HTML landing page |
| 4 | `bmegrowth.es/...v20230926_clean.pdf` | redirect to an unrelated Circular (venue misconfiguration) |

Internet Archive captures of the 2020/2022 URLs are truncated at exactly
1 MiB (compressed record shorter than the document — page catalog lost).

The working channel is the venue's own documents API:

```
https://apiweb.bolsasymercados.es/Market/v1/EQ/MtfEquity/Documents?titleSearch=Reglamento+de+funcionamiento
```

which lists all four rulebook publications as retrievable PDFs today.

## Manifest schema

`manifests/bme_mtf_equity.json` therefore records retrieval *independently*
of the nominal `source_url`:

```json
"retrieval": {
  "discovery_source": "BME Documents API",
  "discovery_endpoint": "...",
  "document_id": "86766",
  "asset_url": "...",
  "retrieved_at": "...",
  "content_type": "application/pdf",
  "byte_size": 1217301,
  "sha256": "..."
}
```

Corroborating sources are recorded separately:

* **v2** — an independent CNMV registry copy (`ReglamentosSMN`).
* **v4** — an archived capture of the venue URL that is byte-identical to
  the live file, plus the official English rulebook.

## Determinism scope

G6 means *deterministic under the declared extraction toolchain*, not
universal determinism across OCR/renderer versions. The toolchain is pinned
in the manifest (`extraction_toolchain`) and reported by
`venue-rule-diff toolchain`:

* PyMuPDF 1.28.2, flags `TEXTFLAGS_DICT | TEXT_CID_FOR_UNKNOWN_UNICODE`
* Tesseract 5.4.0.20240606, `eng` traineddata, 300 dpi render, `--psm 6`

OCR output is used for structural anchors only — never for article body
text — so an OCR-language-model difference cannot silently alter normative
text.

## Copyright

The original PDFs are not redistributed: `data/raw/` is gitignored, and
public output (CLI, `site/`) is limited to change excerpts and diffs. The
repository does not mirror the rulebook.
