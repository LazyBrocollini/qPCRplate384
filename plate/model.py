"""Core data model for a 384-well qPCR plate: well math, targets, sample records, layouts.

Wells are numbered row-major: well 1 = A1, well 24 = A24, well 25 = B1, well 384 = P24.
Internally rows are 0-based (0 = A) and columns are 1-based (1..24), as on the instrument.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

ROW_LETTERS = "ABCDEFGHIJKLMNOP"
N_ROWS = 16
N_COLS = 24
N_WELLS = N_ROWS * N_COLS            # 384
GROUP_SIZE = 3                       # one triplicate = 3 wells
MAX_GROUPS = N_WELLS // GROUP_SIZE   # 128
SAMPLE_ROWS = tuple("ABCDEFGH")
DILUTIONS = ("undiluted", "1to1", "1to2", "1to4")
TASKS = ("UNKNOWN", "NTC")
NTC = "NTC"
DEFAULT_REPORTER = "FAM"
DEFAULT_QUENCHER = "NFQ-MGB"
DEFAULT_PASSIVE = "ROX"
DEFAULT_TEMPLATE = "{sample_row}_row_{condition}_{dilution} {aso_id}"
STRATEGY_KEYS = ("S1", "S2", "S3", "S4")


def _check_well(well: int) -> None:
    if not isinstance(well, int) or isinstance(well, bool) or not 1 <= well <= N_WELLS:
        raise ValueError(f"well number must be 1..{N_WELLS}, got {well!r}")


def well_index(row: int, col: int) -> int:
    """Map a 0-based row (0 = A) and 1-based column to the 1-based well number."""
    if not (0 <= row < N_ROWS and 1 <= col <= N_COLS):
        raise ValueError(f"no well at row {row}, column {col}")
    return row * N_COLS + col


def well_row_col(well: int) -> tuple[int, int]:
    """Return (0-based row, 1-based column) for a well number."""
    _check_well(well)
    return (well - 1) // N_COLS, (well - 1) % N_COLS + 1


def well_position(well: int) -> str:
    """Well number to position label, e.g. 25 -> 'B1'."""
    row, col = well_row_col(well)
    return f"{ROW_LETTERS[row]}{col}"


_POS_RE = re.compile(r"([A-P])([1-9]|1\d|2[0-4])")


def parse_position(text: str) -> int:
    """Position label to well number, e.g. 'b1' -> 25."""
    m = _POS_RE.fullmatch(text.strip().upper())
    if not m:
        raise ValueError(f"bad well position {text!r}")
    return well_index(ROW_LETTERS.index(m.group(1)), int(m.group(2)))


def is_edge_well(well: int) -> bool:
    """True for row P or column 24, the wells the edge guard keeps empty."""
    row, col = well_row_col(well)
    return row == N_ROWS - 1 or col == N_COLS


@dataclass(frozen=True)
class Target:
    """A primer-probe set (Ppset) with its assay ID and display alias."""

    assay_id: str
    alias: str = ""
    reporter: str = DEFAULT_REPORTER
    quencher: str = DEFAULT_QUENCHER
    passive_reference: str = DEFAULT_PASSIVE


@dataclass
class Record:
    """One sample-target pair. Each record is exactly one triplicate group."""

    sample_row: str
    condition: str
    dilution: str
    aso_id: str
    target: str                 # assay ID of the Target
    task: str = "UNKNOWN"
    set_index: int = 1          # 2 for the second NTC set (adds _2 to the name)
    gid: str = ""               # stable group ID, e.g. G001

    @property
    def is_ntc(self) -> bool:
        return self.condition == NTC

    @property
    def is_control(self) -> bool:
        """NTC, 0 nM, or no-ASO controls (used by strategy S3's control row)."""
        return self.is_ntc or self.condition == "0nM" or self.aso_id == "ILC_none"

    def cond_key(self) -> str:
        return f"{self.condition}#{self.set_index}"

    def sample_key(self) -> str:
        """Identity of the sample across targets (everything except the target)."""
        return f"{self.sample_row}|{self.condition}|{self.dilution}|{self.aso_id}|{self.set_index}"

    def copy(self) -> "Record":
        return Record(self.sample_row, self.condition, self.dilution, self.aso_id,
                      self.target, self.task, self.set_index, self.gid)


@dataclass
class PlateSettings:
    """Instrument and naming settings that affect the export."""

    experiment: str = "experiment"
    name_style: str = "space"              # "space" (default) or "underscore"
    name_template: str = DEFAULT_TEMPLATE
    ntc_task: bool = False                 # export Task=NTC for NTC wells when True
    barcode: str = ""
    expected_sample_rows: Optional[int] = None
    expected_conditions: Optional[int] = None
    expected_targets: Optional[int] = None


@dataclass
class Layout:
    """Well assignment for every group, plus the strategy configuration that produced it."""

    strategy: str = "S1"
    edge_guard: bool = False
    seed: Optional[int] = None
    assignments: dict = field(default_factory=dict)   # gid -> tuple of 3 well numbers
    cond_rows: dict = field(default_factory=dict)     # S1: cond_key -> row index in its block
    sample_pos: dict = field(default_factory=dict)    # S4: sample_key -> [row, pair index]

    def copy(self) -> "Layout":
        return Layout(
            strategy=self.strategy,
            edge_guard=self.edge_guard,
            seed=self.seed,
            assignments={k: tuple(v) for k, v in self.assignments.items()},
            cond_rows=dict(self.cond_rows),
            sample_pos={k: list(v) for k, v in self.sample_pos.items()},
        )

    def used_wells(self) -> set:
        used: set = set()
        for wells in self.assignments.values():
            used.update(wells)
        return used

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "edge_guard": self.edge_guard,
            "seed": self.seed,
            "assignments": {k: list(v) for k, v in self.assignments.items()},
            "cond_rows": dict(self.cond_rows),
            "sample_pos": {k: list(v) for k, v in self.sample_pos.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Layout":
        return cls(
            strategy=data.get("strategy", "S1"),
            edge_guard=bool(data.get("edge_guard", False)),
            seed=data.get("seed"),
            assignments={k: tuple(int(w) for w in v) for k, v in data.get("assignments", {}).items()},
            cond_rows={k: int(v) for k, v in data.get("cond_rows", {}).items()},
            sample_pos={k: list(v) for k, v in data.get("sample_pos", {}).items()},
        )


def assign_gids(records: list) -> list:
    """Give every record without a group ID a unique 'G###' ID, in list order."""
    taken = {r.gid for r in records if r.gid}
    n = 1
    for r in records:
        if r.gid:
            continue
        while f"G{n:03d}" in taken:
            n += 1
        r.gid = f"G{n:03d}"
        taken.add(r.gid)
    return records
