# Extraction pipeline

How a rulebook PDF becomes 47 articles + the Final Provision.

```
PDF
 └─ extract_lines()        per-page dict-mode lines (y0,y1,x0,text),
                           PyMuPDF TEXT_CID_FOR_UNKNOWN_UNICODE
     └─ _merge_markers()   standalone list markers ("a)", "1.") merged
                           into their text line by y-proximity
 └─ _text_anchors()        article heading candidates in the text layer
 └─ _body_start()          body = second occurrence of "article 1"
                           (first is the TOC)
 └─ _image_anchors()       OCR of image-strip rows — v2 only
 └─ clean_lines()          drop footers, page numbers, colophon boilerplate
 └─ segment_pdf()          ordered anchors -> article texts; warnings
                           for missing/duplicate/out-of-order/out-of-range
```

## The CID problem

All four PDFs use embedded fonts whose ToUnicode maps are broken or absent —
every extractor (`pdfminer`, `pypdf`, default PyMuPDF, `pdftotext`) returns
U+FFFD for accented characters. The CIDs *are* the Unicode code points, so
`pymupdf.TEXT_CID_FOR_UNKNOWN_UNICODE` recovers full text exactly.

## The v2 problem

The July 2022 version renders **every heading as bitmap strips** — clusters
of small per-glyph images — plus a buggy invisible text overlay:

* 6 headings have no overlay at all (5, 29, 33, 34, 36, 43).
* The overlay that exists is malformed: `A rtículo 18.`, `Artí culo 36.`,
  `Artícu\nlo 42.` split mid-word.
* `Disposición Final` is a centered image, not a margin line.

The extractor handles this with dual detection:

1. A tolerant compacted-form regex accepts every overlay variant.
2. Image-strip rows are clustered by y-range and OCR'd (Tesseract, 300 dpi,
   `--psm 6`, `eng`) — anchors only. **OCR recovers structure; it never
   produces normative body text.** Body text always comes from the native
   text layer.
3. The strict 1–47 sequential check validates the merge; an out-of-order
   OCR label falls back to positional sequence inference.

## TOC vs body

The TOC lists articles 1–47 once; the body repeats them. The body starts at
the second article-1 anchor. The TOC is parsed separately for an integrity
check — a TOC/body mismatch produces a validation **warning**, never a
regulatory change.

## What is excluded, symmetrically

Cover, version-control table, TOC, headers, footers, page numbers,
colophon/Aviso boilerplate, and section (Título) headers. In v2, Título
headers exist only as images, so excluding them symmetrically matters more
than capturing section names — a renamed section header is deliberately not
an article change.

## Normalization

Light-touch and deterministic: NFC, NBSP→space, run-collapse, paragraph
breaks preserved. One documented glyph alias maps a private-use Symbol-font
minus (U+F02D, v4) to U+2212 (v3) — same visual glyph, different encoding.
Normalization never corrects spelling or punctuation differences.
