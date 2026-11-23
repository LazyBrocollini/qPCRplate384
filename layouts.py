"""384-well layouts taken from '384-well quadrants options.xlsx' (sheet 'triplicates').

Each layout is a 16 x 24 grid (rows A-P, columns 1-24). Each cell holds the
96-well position (A1..H12) whose sample goes in that 384 well, or blank.
Generated from the workbook; the values are copied, not recalculated.
"""

ROWS_384 = list("ABCDEFGHIJKLMNOP")
COLS_384 = list(range(1, 25))

LAYOUTS = [
    {
        "key": "one_ppset",
        "name": "Layout 1: one PP set, all triplicates",
        "description": 'Sheet rows 35-50. Q1, Q2, Q3 and Q4 all use the same PP set.',
        "grid": [
            "A1|E1|A2|E2|A3|E3|A4|E4|A5|E5|A6|E6|A7|E7|A8|E8|A9|E9|A10|E10|A11|E11|A12|E12",
            "A1|E1|A2|E2|A3|E3|A4|E4|A5|E5|A6|E6|A7|E7|A8|E8|A9|E9|A10|E10|A11|E11|A12|E12",
            "A1|E1|A2|E2|A3|E3|A4|E4|A5|E5|A6|E6|A7|E7|A8|E8|A9|E9|A10|E10|A11|E11|A12|E12",
            "B1|F1|B2|F2|B3|F3|B4|F4|B5|F5|B6|F6|B7|F7|B8|F8|B9|F9|B10|F10|B11|F11|B12|F12",
            "B1|F1|B2|F2|B3|F3|B4|F4|B5|F5|B6|F6|B7|F7|B8|F8|B9|F9|B10|F10|B11|F11|B12|F12",
            "B1|F1|B2|F2|B3|F3|B4|F4|B5|F5|B6|F6|B7|F7|B8|F8|B9|F9|B10|F10|B11|F11|B12|F12",
            "C1|G1|C2|G2|C3|G3|C4|G4|C5|G5|C6|G6|C7|G7|C8|G8|C9|G9|C10|G10|C11|G11|C12|G12",
            "C1|G1|C2|G2|C3|G3|C4|G4|C5|G5|C6|G6|C7|G7|C8|G8|C9|G9|C10|G10|C11|G11|C12|G12",
            "C1|G1|C2|G2|C3|G3|C4|G4|C5|G5|C6|G6|C7|G7|C8|G8|C9|G9|C10|G10|C11|G11|C12|G12",
            "C1|H1|C2|H2|C3|H3|C4|H4|C5|H5|C6|H6|C7|H7|C8|H8|C9|H9|C10|H10|C11|H11|C12|H12",
            "D1|H1|D2|H2|D3|H3|D4|H4|D5|H5|D6|H6|D7|H7|D8|H8|D9|H9|D10|H10|D11|H11|D12|H12",
            "D1|H1|D2|H2|D3|H3|D4|H4|D5|H5|D6|H6|D7|H7|D8|H8|D9|H9|D10|H10|D11|H11|D12|H12",
            "D1||D2||D3||D4||D5||D6||D7||D8||D9||D10||D11||D12|",
            "E1||E2||E3||E4||E5||E6||E7||E8||E9||E10||E11||E12|",
            "E1||E2||E3||E4||E5||E6||E7||E8||E9||E10||E11||E12|",
            "E1||E2||E3||E4||E5||E6||E7||E8||E9||E10||E11||E12|",
        ],
    },
    {
        "key": "q1q3_q2q4",
        "name": "Layout 2: Q1 and Q3 one PP set, Q2 and Q4 another",
        "description": 'Sheet rows 55-70. Q1 and Q3 use one PP set; Q2 and Q4 use another.',
        "grid": [
            "A1|A1|A2|A2|A3|A3|A4|A4|A5|A5|A6|A6|A7|A7|A8|A8|A9|A9|A10|A10|A11|A11|A12|A12",
            "A1|A1|A2|A2|A3|A3|A4|A4|A5|A5|A6|A6|A7|A7|A8|A8|A9|A9|A10|A10|A11|A11|A12|A12",
            "A1|A1|A2|A2|A3|A3|A4|A4|A5|A5|A6|A6|A7|A7|A8|A8|A9|A9|A10|A10|A11|A11|A12|A12",
            "B1|B1|B2|B2|B3|B3|B4|B4|B5|B5|B6|B6|B7|B7|B8|B8|B9|B9|B10|B10|B11|B11|B12|B12",
            "B1|B1|B2|B2|B3|B3|B4|B4|B5|B5|B6|B6|B7|B7|B8|B8|B9|B9|B10|B10|B11|B11|B12|B12",
            "B1|B1|B2|B2|B3|B3|B4|B4|B5|B5|B6|B6|B7|B7|B8|B8|B9|B9|B10|B10|B11|B11|B12|B12",
            "C1|C1|C2|C2|C3|C3|C4|C4|C5|C5|C6|C6|C7|C7|C8|C8|C9|C9|C10|C10|C11|C11|C12|C12",
            "C1|C1|C2|C2|C3|C3|C4|C4|C5|C5|C6|C6|C7|C7|C8|C8|C9|C9|C10|C10|C11|C11|C12|C12",
            "C1|C1|C2|C2|C3|C3|C4|C4|C5|C5|C6|C6|C7|C7|C8|C8|C9|C9|C10|C10|C11|C11|C12|C12",
            "C1|C1|C2|C2|C3|C3|C4|C4|C5|C5|C6|C6|C7|C7|C8|C8|C9|C9|C10|C10|C11|C11|C12|C12",
            "D1|D1|D2|D2|D3|D3|D4|D4|D5|D5|D6|D6|D7|D7|D8|D8|D9|D9|D10|D10|D11|D11|D12|D12",
            "D1|D1|D2|D2|D3|D3|D4|D4|D5|D5|D6|D6|D7|D7|D8|D8|D9|D9|D10|D10|D11|D11|D12|D12",
            "D1|D1|D2|D2|D3|D3|D4|D4|D5|D5|D6|D6|D7|D7|D8|D8|D9|D9|D10|D10|D11|D11|D12|D12",
            "E1|E1|E2|E2|E3|E3|E4|E4|E5|E5|E6|E6|E7|E7|E8|E8|E9|E9|E10|E10|E11|E11|E12|E12",
            "E1|E1|E2|E2|E3|E3|E4|E4|E5|E5|E6|E6|E7|E7|E8|E8|E9|E9|E10|E10|E11|E11|E12|E12",
            "E1|E1|E2|E2|E3|E3|E4|E4|E5|E5|E6|E6|E7|E7|E8|E8|E9|E9|E10|E10|E11|E11|E12|E12",
        ],
    },
    {
        "key": "column_blocks",
        "name": "Layout 3: column blocks, three PP sets",
        "description": 'Sheet rows 76-91. Columns 1-3 and 10-12 use one PP set; columns 5-7 and 13-15 another; columns 7-9 and 16-18 a third (as written in the sheet).',
        "grid": [
            "A1|A1|A1|A1|A1|A1|A1|A1|A1|A2|A2|A2|A2|A2|A2|A2|A2|A2||||||",
            "A2|A2|A2|A2|A2|A2|A2|A2|A2|A3|A3|A3|A3|A3|A3|A3|A3|A3||||||",
            "B1|B1|B1|B1|B1|B1|B1|B1|B1|B2|B2|B2|B2|B2|B2|B2|B2|B2||||||",
            "B2|B2|B2|B2|B2|B2|B2|B2|B2|B3|B3|B3|B3|B3|B3|B3|B3|B3||||||",
            "C1|C1|C1|C1|C1|C1|C1|C1|C1|C2|C2|C2|C2|C2|C2|C2|C2|C2||||||",
            "C2|C2|C2|C2|C2|C2|C2|C2|C2|C3|C3|C3|C3|C3|C3|C3|C3|C3||||||",
            "D1|D1|D1|D1|D1|D1|D1|D1|D1|D2|D2|D2|D2|D2|D2|D2|D2|D2||||||",
            "D2|D2|D2|D2|D2|D2|D2|D2|D2|D3|D3|D3|D3|D3|D3|D3|D3|D3||||||",
            "E1|E1|E1|E1|E1|E1|E1|E1|E1|E2|E2|E2|E2|E2|E2|E2|E2|E2||||||",
            "E2|E2|E2|E2|E2|E2|E2|E2|E2|E3|E3|E3|E3|E3|E3|E3|E3|E3||||||",
            "F1|F1|F1|F1|F1|F1|F1|F1|F1|F2|F2|F2|F2|F2|F2|F2|F2|F2||||||",
            "F2|F2|F2|F2|F2|F2|F2|F2|F2|F3|F3|F3|F3|F3|F3|F3|F3|F3||||||",
            "G1|G1|G1|G1|G1|G1|G1|G1|G1|G2|G2|G2|G2|G2|G2|G2|G2|G2||||||",
            "G2|G2|G2|G2|G2|G2|G2|G2|G2|G3|G3|G3|G3|G3|G3|G3|G3|G3||||||",
            "H1|H1|H1|H1|H1|H1|H1|H1|H1|H2|H2|H2|H2|H2|H2|H2|H2|H2||||||",
            "H2|H2|H2|H2|H2|H2|H2|H2|H2|H3|H3|H3|H3|H3|H3|H3|H3|H3||||||",
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers (not generated)
# ---------------------------------------------------------------------------

from collections import Counter  # noqa: E402

from plate_names import make_unique  # noqa: E402


def layout_by_key(key: str) -> dict:
    for layout in LAYOUTS:
        if layout["key"] == key:
            return layout
    raise KeyError(key)


def grid_cells(layout: dict) -> list[list[str]]:
    """The layout grid as a 16 x 24 list of 96-well IDs ('' when empty)."""
    return [row.split("|") for row in layout["grid"]]


def quadrant_of(row_384: int, col_384: int) -> str:
    """Quadrant (Q1-Q4) of a 384 well, using the sheet's '384 quadrants labelled' key.

    row_384 is 1-based (A=1), col_384 is 1-based. Checked against the key in the
    workbook: every one of the 384 cells matches.
    """
    shift = 2 if row_384 % 2 == 0 else 0
    return f"Q{((col_384 - 1) + shift) % 4 + 1}"


def wells_per_sample(layout: dict) -> Counter:
    """How many 384 wells each 96-well sample occupies in this layout."""
    counts = Counter(c for row in grid_cells(layout) for c in row if c)
    return Counter(counts.values())


def place_on_384(
    records: list[dict], layout_key: str, unique_repeats: bool = True
) -> tuple[list[dict], list[dict]]:
    """Place named 96-well samples onto a 384 layout.

    records: output of build_records (keys: file, well, unique).
    Returns (placed, missing):
      placed  - one dict per filled 384 well: file, well384, quadrant, source,
                sample, name (name is made unique across repeats if asked).
      missing - named samples whose 96-well position is not in the layout.
    """
    layout = layout_by_key(layout_key)
    grid = grid_cells(layout)

    by_file: dict[str, dict[str, str]] = {}
    for rec in records:
        by_file.setdefault(rec["file"], {})[rec["well"]] = rec["unique"]

    placed: list[dict] = []
    missing: list[dict] = []
    for fname, names96 in by_file.items():
        used = set()
        for i, row in enumerate(grid):
            for j, src in enumerate(row):
                if src and src in names96:
                    used.add(src)
                    placed.append(
                        {
                            "file": fname,
                            "well384": f"{ROWS_384[i]}{j + 1}",
                            "quadrant": quadrant_of(i + 1, j + 1),
                            "source": src,
                            "sample": names96[src],
                            "name": "",
                        }
                    )
        for well, sample in names96.items():
            if well not in used:
                missing.append({"file": fname, "well": well, "sample": sample})

    names = [p["sample"] for p in placed]
    final = make_unique(names) if unique_repeats else names
    for p, name in zip(placed, final):
        p["name"] = name
    return placed, missing
