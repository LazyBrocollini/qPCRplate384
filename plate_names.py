"""Parsing and naming logic for 96-well (8 x 12) tables.

Pure Python (no Streamlit) so it can be tested on its own.

Expected layout: a title row (e.g. "Replicate"), then a row of column numbers,
then eight rows labelled A-H. A well is identified by its row letter and its
column number (A1..H12), taken from position, so a blank column-number header
does not shift the data.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from dataclasses import dataclass, field

ROWS = list("ABCDEFGH")
COLS = list(range(1, 13))
WELLS = [f"{r}{c}" for r in ROWS for c in COLS]  # row-major, A1..H12


@dataclass
class Table:
    """One 8 x 12 block found in a file."""

    title: str
    values: dict[str, str] = field(default_factory=dict)  # "A1" -> cell text

    @property
    def has_data(self) -> bool:
        return any(v for v in self.values.values())


def _decode(raw: bytes) -> str:
    """Decode uploaded bytes; handle UTF-8 BOM and Windows-1252 exports."""
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_tables(raw: bytes) -> list[Table]:
    """Find every 8 x 12 block in a CSV file, in file order."""
    text = _decode(raw).lstrip("\ufeff")
    rows = list(csv.reader(io.StringIO(text)))

    def cell(r: int, c: int) -> str:
        if 0 <= r < len(rows) and 0 <= c < len(rows[r]):
            return rows[r][c].strip()
        return ""

    tables: list[Table] = []
    for r in range(len(rows)):
        for c in range(len(rows[r]) if r < len(rows) else 0):
            # A block starts where column c reads A, B, ..., H going down.
            if not all(cell(r + i, c) == ROWS[i] for i in range(len(ROWS))):
                continue

            # Title = first non-empty cell of the header row just above row A.
            title = ""
            header_row = rows[r - 1] if r >= 1 else []
            for h in header_row:
                if h.strip():
                    title = h.strip()
                    break
            title = title or f"Table {len(tables) + 1}"

            table = Table(title=title)
            for i, row_letter in enumerate(ROWS):
                for j, col_num in enumerate(COLS):
                    table.values[f"{row_letter}{col_num}"] = cell(r + i, c + 1 + j)
            tables.append(table)

    return tables


def combine_name(parts: list[str]) -> str:
    """Join the non-empty parts with underscores."""
    return "_".join(p for p in parts if p)


def make_unique(names: list[str]) -> list[str]:
    """Make names unique by appending _1, _2, ... to repeats.

    The first occurrence keeps its name. Empty names stay empty. A suffixed
    name never matches any name already in the list, so an existing name such
    as "X_1" is not overwritten.
    """
    original = set(n for n in names if n)
    used: set[str] = set()
    result: list[str] = []
    for name in names:
        if not name:
            result.append("")
            continue
        if name not in used:
            used.add(name)
            result.append(name)
            continue
        k = 1
        while f"{name}_{k}" in used or f"{name}_{k}" in original:
            k += 1
        candidate = f"{name}_{k}"
        used.add(candidate)
        result.append(candidate)
    return result


def build_records(
    files: list[tuple[str, list[Table]]], selected_titles: set[str]
) -> list[dict]:
    """Combine selected tables into one name per well, then make names unique.

    Returns one record per well that has data, in file order then A1..H12.
    Uniqueness is checked across all files together.
    """
    records: list[dict] = []
    for filename, tables in files:
        chosen = [t for t in tables if t.title in selected_titles]
        for well in WELLS:
            parts = [t.values.get(well, "") for t in chosen]
            combined = combine_name(parts)
            if not combined:
                continue
            records.append(
                {
                    "file": filename,
                    "well": well,
                    "combined": combined,
                    "unique": "",
                }
            )

    uniques = make_unique([r["combined"] for r in records])
    for rec, uname in zip(records, uniques):
        rec["unique"] = uname
    return records


def count_repeats(names: list[str]) -> int:
    """How many names were repeated (occurrences beyond the first)."""
    return sum(n - 1 for n in Counter(x for x in names if x).values() if n > 1)
