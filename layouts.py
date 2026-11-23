"""384-well triplicate layouts, based on '384-well quadrants options.xlsx'
(sheet 'triplicates').

Every sample gets exactly 3 wells per PP set.

Layout 1: one PP set, 96 samples x 3 wells = 288 wells
    Four 3-row bands (rows A-C, D-F, G-I, J-L). Each band holds two 96-well
    rows: the first in odd columns, the second in even columns.
    Band pairs: A+E, B+F, C+G, D+H. Rows M-P are empty.

Layout 2: two PP sets, 60 samples x 3 wells per PP set = 360 wells
    Five 3-row bands (rows A-O). Each band is one 96-well row.
    Odd columns (Q1/Q3) are PP set 1, even columns (Q2/Q4) are PP set 2.
    Row P is empty.

Check against the workbook (verified cell by cell):
  * The quadrant key matches all 384 cells of the workbook's quadrant table.
  * The workbook's own layouts do not give every sample exactly 3 wells.
    Layout 1 has 72 samples x3, 12 x4 and 12 x2. Layout 2 has 48 x3 and
    12 x4 per PP set. This module keeps the workbook's band pattern and
    changes only the cells that break the triplicate rule:
      - Layout 1: row J and rows M-P differ from the workbook.
      - Layout 2: rows J, M and P differ from the workbook.
  * A third workbook layout (column blocks, rows 72-91) was not included:
    it covers only 24 of the 96 positions and does not give all samples
    triplicates.
"""

from collections import Counter

ROWS_96 = list("ABCDEFGH")
ROWS_384 = list("ABCDEFGHIJKLMNOP")
COLS_384 = list(range(1, 25))


def _grid_layout_1() -> list[list[str]]:
    grid = [["" for _ in COLS_384] for _ in ROWS_384]
    pairs = [("A", "E"), ("B", "F"), ("C", "G"), ("D", "H")]
    for band, (odd_row, even_row) in enumerate(pairs):
        for r in range(band * 3, band * 3 + 3):
            for k in range(1, 13):
                grid[r][2 * k - 2] = f"{odd_row}{k}"  # column 2k-1
                grid[r][2 * k - 1] = f"{even_row}{k}"  # column 2k
    return grid


def _grid_layout_2() -> list[list[str]]:
    grid = [["" for _ in COLS_384] for _ in ROWS_384]
    for band, row in enumerate(list("ABCDE")):
        for r in range(band * 3, band * 3 + 3):
            for k in range(1, 13):
                grid[r][2 * k - 2] = f"{row}{k}"  # PP set 1 (odd column)
                grid[r][2 * k - 1] = f"{row}{k}"  # PP set 2 (even column)
    return grid


LAYOUTS = [
    {
        "key": "one_ppset",
        "name": "Layout 1: one PP set, triplicates (96 samples)",
        "description": (
            "One PP set. Each sample gets 3 wells in a column of a 3-row band. "
            "Rows A-L hold 96 samples; rows M-P stay empty."
        ),
        "pp_sets": ["PP set"],
        "grid": _grid_layout_1(),
    },
    {
        "key": "two_ppset",
        "name": "Layout 2: two PP sets, triplicates each (60 samples)",
        "description": (
            "Two PP sets. Each sample gets 3 wells with PP set 1 (Q1/Q3 columns) "
            "and 3 wells with PP set 2 (Q2/Q4 columns). Rows A-O hold 60 samples; "
            "row P stays empty."
        ),
        "pp_sets": ["PP set 1", "PP set 2"],
        "grid": _grid_layout_2(),
    },
]


def layout_by_key(key: str) -> dict:
    for layout in LAYOUTS:
        if layout["key"] == key:
            return layout
    raise KeyError(key)


def quadrant_of(row_384: int, col_384: int) -> str:
    """Quadrant (Q1-Q4) of a 384 well. row_384 and col_384 are 1-based.

    Matches every cell of the workbook's quadrant key (checked).
    """
    shift = 2 if row_384 % 2 == 0 else 0
    return f"Q{((col_384 - 1) + shift) % 4 + 1}"


def pp_index(layout: dict, col_384: int) -> int:
    """0-based PP set for a column. Two-PP layouts use odd columns for set 1."""
    if len(layout["pp_sets"]) == 1:
        return 0
    return 0 if col_384 % 2 == 1 else 1


def wells_per_sample(layout: dict) -> Counter:
    """{wells per sample: number of samples} across all PP sets."""
    counts = Counter(cell for row in layout["grid"] for cell in row if cell)
    return Counter(counts.values())


def place_on_384(records: list[dict], layout_key: str) -> tuple[list[dict], list[dict]]:
    """Place named 96-well samples onto a 384 layout.

    records: output of plate_names.build_records (keys: file, well, combined, unique).
    Replicate wells of one sample share its name (unique name from step 1), as in
    the instrument reference file.

    Returns (placed, missing):
      placed  - one dict per filled 384 well: file, well384, quadrant, pp_set
                (0-based), source (96 well), sample (name).
      missing - named samples whose 96-well position is not on this layout.
    """
    layout = layout_by_key(layout_key)
    grid = layout["grid"]

    by_file: dict[str, dict[str, dict]] = {}
    for rec in records:
        by_file.setdefault(rec["file"], {})[rec["well"]] = rec

    placed: list[dict] = []
    missing: list[dict] = []
    for fname, recs96 in by_file.items():
        used = set()
        for i, row in enumerate(grid):
            for j, src in enumerate(row):
                if src and src in recs96:
                    used.add(src)
                    placed.append(
                        {
                            "file": fname,
                            "well384": f"{ROWS_384[i]}{j + 1}",
                            "quadrant": quadrant_of(i + 1, j + 1),
                            "pp_set": pp_index(layout, j + 1),
                            "source": src,
                            "sample": recs96[src]["unique"],
                        }
                    )
        for well, rec in recs96.items():
            if well not in used:
                missing.append({"file": fname, "well": well, "sample": rec["unique"]})

    placed.sort(key=lambda p: (ROWS_384.index(p["well384"][0]), int(p["well384"][1:])))
    return placed, missing
