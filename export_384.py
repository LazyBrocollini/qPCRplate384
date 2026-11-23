"""Instrument import TXT for a 384-well plate.

Matches qpcr_384_import_format_reference.txt:
  * Windows-1252 encoding, CRLF line endings, final CRLF.
  * 4 preamble lines (each padded with 11 tabs), a blank line, [Sample Setup],
    a 12-column header, then all 384 wells in row-major order (A1..P24).
  * Empty wells keep only Well and Well Position; the other fields are blank.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from layouts import COLS_384, ROWS_384

ENCODING = "cp1252"
NEWLINE = "\r\n"
HEADER = [
    "Well",
    "Well Position",
    "Sample Name",
    "Sample Color",
    "Biogroup Name",
    "Biogroup Color",
    "Target Name",
    "Target Color",
    "Task",
    "Reporter",
    "Quencher",
    "Quantity",
]
N_FIELDS = len(HEADER)  # 12

TASK = "UNKNOWN"
PASSIVE_REFERENCE = "ROX"
BLOCK_TYPE = "384-Well Block"
TIMEZONE = "America/Los_Angeles"

# Dropdown choices. Dye is written to the Reporter column.
QUENCHERS = ["NFQ-MGB", "TAMRA", "BHQ-1"]
DYES = ["FAM", "VIC", "HEX", "TET", "JOE", "NED", "Cy5"]
DEFAULT_QUENCHER = "NFQ-MGB"
DEFAULT_DYE = "FAM"

PPSET_FILE = Path(__file__).with_name("ppsets.csv")
DEFAULT_TARGETS = ["ACTN1_HTS5001", "ACTB_Hs01060665_g1"]


def load_pp_targets(path: Path = PPSET_FILE) -> list[str]:
    """Target names from the PP set table (column 'Target Name').

    Falls back to the two reference targets if the file is missing or empty.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            names = [row["Target Name"].strip() for row in csv.DictReader(fh)]
    except (OSError, KeyError):
        return list(DEFAULT_TARGETS)
    names = [n for n in names if n]
    return names or list(DEFAULT_TARGETS)


def _clean(text: str) -> str:
    """Remove characters that would break the tab/line structure."""
    return str(text).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def _line(*fields: str) -> str:
    return "\t".join(fields)


def well_label(n: int) -> str:
    """Well position for well number n (1..384), row-major."""
    row = ROWS_384[(n - 1) // len(COLS_384)]
    col = (n - 1) % len(COLS_384) + 1
    return f"{row}{col}"


def render_import_txt(
    wells: dict[str, tuple[str, str]],
    quencher: str,
    dye: str,
    now: datetime | None = None,
) -> bytes:
    """Build the instrument TXT.

    wells: {"A1": (sample_name, target_name), ...} for filled wells only.
    Returns Windows-1252 bytes with CRLF line endings.
    """
    now = now or datetime.now(ZoneInfo(TIMEZONE))
    blank = [""] * (N_FIELDS - 1)
    lines = [
        _line(f"* Block Type = {BLOCK_TYPE}", *blank),
        _line(f"* Date Created = {now.strftime('%a %b %d %H:%M:%S %Z %Y')}", *blank),
        _line(f"* Passive Reference = {PASSIVE_REFERENCE}", *blank),
        _line("* Barcode = ", *blank),
        _line(*([""] * N_FIELDS)),
        _line("[Sample Setup]", *blank),
        _line(*HEADER),
    ]
    for n in range(1, len(ROWS_384) * len(COLS_384) + 1):
        pos = well_label(n)
        if pos in wells:
            sample, target = wells[pos]
            sample = _clean(sample)
            target = _clean(target)
            fields = [
                str(n), pos,
                sample, "", sample, "",  # Sample, Sample Color, Biogroup, Biogroup Color
                target, "",              # Target Name, Target Color
                TASK, _clean(dye), _clean(quencher), "",
            ]
        else:
            fields = [str(n), pos] + [""] * (N_FIELDS - 2)
        lines.append(_line(*fields))
    text = NEWLINE.join(lines) + NEWLINE
    return text.encode(ENCODING)


def validate_import_txt(data: bytes) -> list[str]:
    """Return a list of problems (empty list means the file passes)."""
    problems: list[str] = []
    try:
        text = data.decode(ENCODING)
    except UnicodeDecodeError as exc:
        return [f"not Windows-1252: {exc}"]
    if data.count(b"\n") != data.count(b"\r\n"):
        problems.append("bare LF found (line endings must be CRLF)")
    if not data.endswith(b"\r\n"):
        problems.append("missing final CRLF")
    lines = text.split(NEWLINE)[:-1]
    if len(lines) != 7 + 384:
        problems.append(f"expected {7 + 384} lines, found {len(lines)}")
    if lines[5] != "[Sample Setup]" + "\t" * (N_FIELDS - 1):
        problems.append("missing [Sample Setup] line")
    if lines[6] != "\t".join(HEADER):
        problems.append("header does not match the reference columns")
    for i, line in enumerate(lines[7:], start=1):
        fields = line.split("\t")
        if len(fields) != N_FIELDS:
            problems.append(f"row {i} has {len(fields)} fields, expected {N_FIELDS}")
            break
        if fields[0] != str(i) or fields[1] != well_label(i):
            problems.append(f"row {i} is {fields[0]}/{fields[1]}, expected {i}/{well_label(i)}")
            break
        if fields[2] and fields[8] != TASK:
            problems.append(f"row {i}: task is {fields[8]!r}, expected {TASK!r}")
            break
    return problems
