"""Layout strategies S1 to S4, auto-placement, and the slot catalog.

Every strategy is described by a *slot catalog*: the list of triplicate positions it allows.
Auto-placement, manual edits, and validation all use the same catalog, so a group can only
exist where its strategy's grid allows it.

S1  Row-block horizontal triplicates. Each target owns a block of rows (16 // T rows). Within a
    block, each plate row is one condition level; each sample row letter A to H is one group
    column (cols 1-3, 4-6, ... 22-24). Target 1 in rows A-H and target 2 in rows I-P for T = 2.
S2  Quadrant 2x2 blocks, 96 blocks. Q1, Q2, Q3 form the triplicate; Q4 stays empty.
S3  Vertical triplicates: rows A-O in 5 blocks of 3 rows, 24 columns (120 groups). Row P holds
    8 horizontal control groups. Single target only.
S4  Target-paired sample rows: each sample's targets sit side by side in one row.

Edge guard (hard): when on, row P and column 24 are never used.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from .model import (N_COLS, N_ROWS, Layout, Record, Target, well_index, well_position)

STRATEGY_NAMES = {
    "S1": "S1 Row-block horizontal triplicates",
    "S2": "S2 Quadrant 2x2 blocks",
    "S3": "S3 Vertical triplicates + control row",
    "S4": "S4 Target-paired sample rows",
}
REASONS = {
    "S1": "Row-block grid: one plate row per condition level, one column group per sample row. "
          "Matches the attached layout.",
    "S2": "Quadrant blocks: one 2x2 block per sample-target pair (up to 96). Replicates are spread across the plate.",
    "S3": "Vertical triplicates with a reserved control row (single target, up to 120 samples + 8 controls).",
    "S4": "Target-paired rows: both targets for one sample sit side by side.",
}
CAPACITY = {"S1": "128 groups per plate (16 // targets rows per target)", "S2": "96 groups",
            "S3": "120 sample groups + 8 control groups", "S4": "64 samples for two targets; 128 for one"}


class CapacityError(ValueError):
    """Raised when records cannot be placed under the chosen strategy."""


@dataclass(frozen=True)
class Slot:
    wells: tuple            # sorted tuple of 3 well numbers
    container: str          # used for gap counting (a row, column, pair, or block)
    target_idx: Optional[int] = None   # S1 block owner or S4 position; None = any target
    kind: str = "sample"    # "sample", "control", or "block"


def s1_wells(plate_row: int, group_col: int) -> tuple:
    """Horizontal triplicate in a plate row; group_col 0..7 covers columns 1-3 ... 22-24."""
    c0 = 3 * group_col + 1
    return tuple(well_index(plate_row, c0 + k) for k in range(3))


def s2_wells(block_row: int, block_col: int) -> tuple:
    """Q1 top-left, Q2 top-right, Q3 bottom-left. Q4 (bottom-right) is never used."""
    r, c = 2 * block_row, 2 * block_col + 1
    return tuple(sorted((well_index(r, c), well_index(r, c + 1), well_index(r + 1, c))))


def s3_wells(block: int, col: int) -> tuple:
    """Vertical triplicate: block 0..4 covers rows 3b..3b+2; col 0..23 is column col+1."""
    return tuple(sorted(well_index(3 * block + k, col + 1) for k in range(3)))


def group_count_per_target_s1(n_targets: int) -> int:
    return (N_ROWS // n_targets) * 8


@lru_cache(maxsize=None)
def catalog(strategy: str, n_targets: int, edge_guard: bool) -> tuple:
    """Every triplicate position the strategy allows, in fill order."""
    t_count = max(1, n_targets)
    out = []
    if strategy == "S1":
        rpb = N_ROWS // t_count
        if rpb < 1:
            raise CapacityError(f"S1 supports at most {N_ROWS} targets; got {n_targets}.")
        for t in range(t_count):
            for ri in range(rpb):
                row = t * rpb + ri
                for g in range(8):
                    if edge_guard and (row == N_ROWS - 1 or g == 7):
                        continue
                    out.append(Slot(s1_wells(row, g), f"S1:row{row + 1}", t, "block"))
    elif strategy == "S2":
        for br in range(8):
            for bc in range(12):
                if edge_guard and (br == 7 or bc == 11):
                    continue
                out.append(Slot(s2_wells(br, bc), f"S2:{br}:{bc}", None, "block"))
    elif strategy == "S3":
        for c in range(N_COLS):
            if edge_guard and c == N_COLS - 1:
                continue
            for b in range(5):
                out.append(Slot(s3_wells(b, c), f"S3:col{c + 1}", None, "sample"))
        if not edge_guard:
            for g in range(8):
                out.append(Slot(s1_wells(N_ROWS - 1, g), "S3:controls", None, "control"))
    elif strategy == "S4":
        usable = 7 if edge_guard else 8
        per_row = usable // t_count
        rows = N_ROWS - 1 if edge_guard else N_ROWS
        for r in range(rows):
            for p in range(per_row):
                for j in range(t_count):
                    out.append(Slot(s1_wells(r, p * t_count + j), f"S4:{r + 1}:{p}", j, "sample"))
    else:
        raise ValueError(f"unknown strategy {strategy!r}")
    return tuple(out)


@lru_cache(maxsize=None)
def allowed_shapes(strategy: str, n_targets: int, edge_guard: bool, target_idx: Optional[int]) -> dict:
    """Map frozenset(3 wells) -> Slot for every slot a record of this target may use."""
    shapes = {}
    for slot in catalog(strategy, n_targets, edge_guard):
        if slot.target_idx is None or target_idx is None or slot.target_idx == target_idx:
            shapes[frozenset(slot.wells)] = slot
    return shapes


def group_wells_for_start(strategy: str, start: int) -> tuple:
    """Wells a group would occupy when its start (top-left) well is `start`."""
    if strategy in ("S1", "S4"):
        wells = (start, start + 1, start + 2)
    elif strategy == "S2":
        wells = (start, start + 1, start + N_COLS)
    elif strategy == "S3":
        wells = (start, start + N_COLS, start + 2 * N_COLS)
    else:
        raise ValueError(strategy)
    if wells[-1] > 384:
        raise CapacityError("group would run past the end of the plate")
    return wells


def _free_slots(slots, occupied: set) -> list:
    return [s for s in slots if not any(w in occupied for w in s.wells)]


def place_records(records: list, targets: list, layout: Layout) -> Layout:
    """Place every record that has no wells yet. Returns a new Layout; raises CapacityError.

    `records` is the full record list (condition order follows its order). Records that are
    already placed keep their wells, so this also serves manual 'add sample' placement.
    """
    if not targets:
        raise CapacityError("Add at least one target before placing samples.")
    tindex = {t.assay_id: i for i, t in enumerate(targets)}
    if any(not r.gid for r in records):
        raise CapacityError("every sample row needs a group ID (call assign_gids first).")
    for r in records:
        if r.target not in tindex:
            raise CapacityError(f"Target {r.target!r} is not in the targets table.")
    lay = layout.copy()
    pending = [r for r in records if r.gid not in lay.assignments]
    if not pending:
        return lay
    occupied = lay.used_wells()
    if lay.strategy == "S1":
        _place_s1(records, pending, lay, occupied, tindex, len(targets))
    elif lay.strategy == "S2":
        _place_s2(pending, lay, occupied, len(targets))
    elif lay.strategy == "S3":
        _place_s3(pending, lay, occupied, len(targets))
    elif lay.strategy == "S4":
        _place_s4(pending, lay, occupied, tindex, len(targets))
    else:
        raise CapacityError(f"unknown strategy {lay.strategy!r}")
    return lay


def _place_s1(all_records, pending, lay, occupied, tindex, n_targets):
    rpb = N_ROWS // n_targets
    if not lay.cond_rows:
        keys = list(dict.fromkeys(r.cond_key() for r in all_records))
        if lay.seed is not None:
            random.Random(lay.seed).shuffle(keys)
        lay.cond_rows = {k: i for i, k in enumerate(keys)}
    for rec in pending:
        key = rec.cond_key()
        if key not in lay.cond_rows:
            lay.cond_rows[key] = len(lay.cond_rows)
        ri = lay.cond_rows[key]
        name = f"{rec.sample_row} {rec.condition} ({rec.target})"
        if ri >= rpb:
            raise CapacityError(
                f"{n_targets} target(s) leave {rpb} rows per target, but this design has {ri + 1} "
                f"condition levels. Reduce the condition levels or the targets.")
        g = ord(rec.sample_row) - ord("A")
        if not 0 <= g <= 7:
            raise CapacityError(f"{name}: S1 takes sample rows A to H only.")
        row = tindex[rec.target] * rpb + ri
        if lay.edge_guard and g == 7:
            raise CapacityError(f"{name}: S1 puts sample row H in columns 22-24, which includes column 24. "
                                "With the edge guard on, S1 holds sample rows A to G only. Turn the guard "
                                "off, or use S2 or S4.")
        if lay.edge_guard and row == N_ROWS - 1:
            raise CapacityError(f"{name}: this condition level needs row P, which the edge guard keeps empty.")
        wells = s1_wells(row, g)
        clash = [w for w in wells if w in occupied]
        if clash:
            raise CapacityError(f"{name}: grid cell {well_position(wells[0])} is already used.")
        lay.assignments[rec.gid] = wells
        occupied.update(wells)


def _place_s2(pending, lay, occupied, n_targets):
    order = list(catalog("S2", n_targets, lay.edge_guard))
    if lay.seed is not None:
        random.Random(lay.seed).shuffle(order)
    free = _free_slots(order, occupied)
    for rec in pending:
        if not free:
            raise CapacityError("No free quadrant block left (96 blocks; 77 with the edge guard).")
        slot = free.pop(0)
        lay.assignments[rec.gid] = slot.wells
        occupied.update(slot.wells)


def _place_s3(pending, lay, occupied, n_targets):
    if n_targets != 1:
        raise CapacityError("S3 is for one target. Use S1, S2, or S4 with several targets.")
    slots = catalog("S3", 1, lay.edge_guard)
    samples = [s for s in slots if s.kind == "sample"]
    controls = [s for s in slots if s.kind == "control"]
    if lay.seed is not None:
        random.Random(lay.seed).shuffle(samples)
        random.Random(lay.seed + 1).shuffle(controls)
    for rec in pending:
        if rec.is_control:
            free = _free_slots(controls, occupied)
            if not free:
                raise CapacityError(
                    "S3 keeps controls in row P (8 groups). No control slot is free"
                    + (" because the edge guard removes row P." if lay.edge_guard else "."))
            slot = free[0]
        else:
            free = _free_slots(samples, occupied)
            if not free:
                raise CapacityError("S3 sample area is full (120 groups).")
            slot = free[0]
        lay.assignments[rec.gid] = slot.wells
        occupied.update(slot.wells)


def _place_s4(pending, lay, occupied, tindex, n_targets):
    usable = 7 if lay.edge_guard else 8
    per_row = usable // n_targets
    if per_row < 1:
        raise CapacityError(f"S4 needs at least {n_targets} usable groups per row; "
                            f"{usable} are available.")
    rows = N_ROWS - 1 if lay.edge_guard else N_ROWS
    order = [(r, p) for r in range(rows) for p in range(per_row)]
    if lay.seed is not None:
        random.Random(lay.seed).shuffle(order)
    used_pairs = {tuple(v) for v in lay.sample_pos.values()}
    for rec in pending:
        key = rec.sample_key()
        if key not in lay.sample_pos:
            choice = next((pos for pos in order if pos not in used_pairs), None)
            if choice is None:
                raise CapacityError(f"S4 holds {len(order)} samples; no free pair is left.")
            lay.sample_pos[key] = [choice[0], choice[1]]
            used_pairs.add(choice)
        row, pair = lay.sample_pos[key]
        g = pair * n_targets + tindex[rec.target]
        wells = s1_wells(row, g)
        if any(w in occupied for w in wells):
            raise CapacityError(f"S4 pair for {rec.sample_row} is already used.")
        lay.assignments[rec.gid] = wells
        occupied.update(wells)


def auto_place(records: list, targets: list, strategy: str, edge_guard: bool = False,
               seed: Optional[int] = None) -> Layout:
    """Fill the chosen strategy grid from scratch, in input order (shuffled when a seed is set)."""
    if strategy not in STRATEGY_NAMES:
        raise CapacityError(f"unknown strategy {strategy!r}")
    layout = Layout(strategy=strategy, edge_guard=edge_guard, seed=seed)
    return place_records(records, targets, layout)


def recommend(records: list, targets: list, edge_guard: bool = False, seed: Optional[int] = None):
    """Auto mode: the first strategy in preference order that places every record.

    Returns (strategy, reason, layout_or_None).
    """
    if not records or not targets:
        return "S1", "Add samples and targets first.", None
    failures = []
    for s in ("S1", "S2", "S3", "S4"):
        try:
            return s, REASONS[s], auto_place(records, targets, s, edge_guard, seed)
        except CapacityError as exc:
            failures.append(f"{s}: {exc}")
    return "S1", "No strategy fits this design. " + " | ".join(failures), None
