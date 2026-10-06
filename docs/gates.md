# Validation gates

Implemented in `tests/test_gates.py` (skipped when `data/raw/` PDFs are
absent). Final results against the real corpus:

| Gate | Result |
|---|---|
| G0 source availability | **PASS** — 4/4 official versions recovered |
| G1 structural extraction | **PASS** — 47/47 + Final Provision × 4 |
| G2 parser robustness | **PASS** — artefacts covered by fixtures/tests |
| G3 v1→v2 oracle | **PASS** — detected `{16, 18}` exactly |
| G4a declared recall | **PASS** — 26/26 declared changes detected |
| G4b undeclared control | **PASS** — `{14}` verified, 0 unexplained |
| G5 v3→v4 transversal | **PASS** — 8 articles + 1 shared event |
| G6 determinism | **PASS** — byte-identical under declared toolchain |

## Definitions

**G1 — structural integrity.** Articles 1–47 each extracted exactly once,
Disposición Final extracted once, sequential order, no silent content
drop. TOC checked separately; discrepancies are warnings, not changes.

**G2 — parser robustness.** Synthetic fixtures + a generated mini-rulebook
PDF cover: `Artículo N.-`, `Artículo N-`, `Artículo N Título`, footer and
page-number noise, wrapped titles, mid-word split headings
(`A rtículo 18.`, `Artí culo 36.`, `Artícu\nlo 42.`), list markers rendered
as separate positioned spans, and article cross-references in body prose.

**G3 — v1→v2 oracle.** `detected == {16, 18}`.

**G4 — v2→v3 oracle, reformulated.** Originally an equality-of-sets test
(`detected == declared`). The corpus forced a stronger formulation:

* **G4a — declared-change recall**: `declared ⊆ detected` → 26/26.
* **G4b — undeclared-change control**: `detected − declared` must equal a
  set of verified exceptions with evidence in the source bytes —
  `{14}` — and `unexplained_extra_changes == 0`.

Article 14 differs between the v2 and v3 source documents —
`"Miembro de la Bolsa. y de las que"` → `"Miembro de la Bolsa y de las
que"` — a real punctuation correction the venue never declared. It is
surfaced (classified `formatting`) rather than suppressed: the product
compares real documents, not change logs. G4 thereby demonstrates that the
BME change log is not exhaustive.

Result: `declared=26, detected=27, declared_detected=26,
verified_undeclared=1, unexplained=0`.

**G5 — v3→v4 transversal terminology.** The changed-article set must equal
exactly the articles containing `BME Scale` in v3 → `{1, 13, 15, 16, 18,
19, 21, 26}`. The shared substitution appears once as a
`global_change_event` while each article keeps its own word-level diff —
two levels of truth, no suppression.

**G6 — determinism.** Repeated extraction and diff of identical bytes must
produce identical normalized content and identical diff output — under the
declared toolchain (see [provenance](provenance.md)).
