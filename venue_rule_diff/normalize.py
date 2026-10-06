"""Deterministic text normalization for article content.

Normalization is intentionally light-touch: it must erase pagination and
extraction artefacts while preserving every real textual difference.  It
never fixes spelling, never removes punctuation and never reorders.
"""

from __future__ import annotations

import re
import unicodedata

_WS_RUN = re.compile(r"[ \t ]+")


# Font-encoding artefacts observed in the corpus: identical visual glyphs
# encoded through private-use code points in one version only.
_GLYPH_ALIASES = {
    "": "−",   # Symbol-font minus (v4) == U+2212 minus sign (v3)
}


def normalize_text(text: str) -> str:
    """Normalize extracted article text for comparison.

    * NFC unicode normalization, NBSP -> space.
    * Known font-encoding aliases mapped to their canonical glyph.
    * Trailing whitespace per line removed, interior runs collapsed.
    * Paragraph breaks (blank lines) preserved as ``\\n\\n``.
    """
    text = unicodedata.normalize("NFC", text)
    for a, b in _GLYPH_ALIASES.items():
        text = text.replace(a, b)
    out_lines: list[str] = []
    for line in text.split("\n"):
        line = _WS_RUN.sub(" ", line).strip()
        out_lines.append(line)
    # collapse >1 consecutive blank lines
    res: list[str] = []
    blank = False
    for line in out_lines:
        if line == "":
            if not blank:
                res.append("")
            blank = True
        else:
            res.append(line)
            blank = False
    return "\n".join(res).strip()


_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def tokenize(text: str) -> list[str]:
    """Split normalized text into word/punctuation tokens for word diffs."""
    return _TOKEN_RE.findall(text)
