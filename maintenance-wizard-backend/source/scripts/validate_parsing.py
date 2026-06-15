"""Parsing validation harness.

Parses the sample ingestion documents and prints the section structure the RAG
pipeline derives, then asserts that section counts stay in a sane range. This
makes parser regressions (over-segmentation, header/footer leakage, shredded
tables) visible immediately instead of surfacing as poor retrieval later.

Run from the project root:

    venv\\Scripts\\python.exe src\\scripts\\validate_parsing.py

Exits non-zero if any expectation fails, so it can gate CI.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a plain script: make ``src`` importable.
_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from rag.parsing import parse_document  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):  # avoid cp1252 crashes on Windows consoles
    sys.stdout.reconfigure(encoding="utf-8")

_SAMPLE_DIR = _SRC / "docs" / "sample_docs_for_ingestion"

# Per-file expectations: (min_sections, max_sections). Bounds are deliberately
# loose — they catch the ~5x over-segmentation regression, not exact counts.
_EXPECTATIONS: dict[str, tuple[int, int]] = {
    "Code of Practice for Raw Material Spillage Control.pdf": (5, 35),
    "SPECIFICATION FOR CHAIN WHEELS.pdf": (4, 20),
}


def _report(path: Path) -> tuple[int, int]:
    """Print one document's section breakdown. Returns (sections, tables)."""
    full_text, sections = parse_document(path)
    tables = sum(1 for s in sections if s.is_table)
    print(f"\n{'=' * 88}\n{path.name}")
    print(f"  full_text: {len(full_text)} chars   sections: {len(sections)}   tables: {tables}")
    for i, s in enumerate(sections):
        tag = "TABLE" if s.is_table else "     "
        print(f"  [{i:2}] L{s.heading_level} p{s.page_number:<2} {tag} ~{s.token_estimate:4}t  {s.heading!r}")
    return len(sections), tables


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    scan_all = "--all" in argv  # --all parses the entire sample corpus (slow)

    if not _SAMPLE_DIR.exists():
        print(f"Sample directory not found: {_SAMPLE_DIR}", file=sys.stderr)
        return 2

    if scan_all:
        pdfs = sorted(_SAMPLE_DIR.rglob("*.pdf"))
    else:
        # Default: just the documents we have expectations for (fast gate).
        pdfs = sorted(
            p for p in _SAMPLE_DIR.rglob("*.pdf") if p.name in _EXPECTATIONS
        )
    if not pdfs:
        print(f"No sample PDFs under {_SAMPLE_DIR}", file=sys.stderr)
        return 2

    failures: list[str] = []
    for pdf in pdfs:
        count, _tables = _report(pdf)
        bounds = _EXPECTATIONS.get(pdf.name)
        if bounds is None:
            continue
        low, high = bounds
        if not (low <= count <= high):
            failures.append(
                f"{pdf.name}: {count} sections outside expected [{low}, {high}]"
            )

    print(f"\n{'=' * 88}")
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"OK: parsed {len(pdfs)} document(s); all checked files within expected bounds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
