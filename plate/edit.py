"""Manual edits: move a group to a start well, clear groups, add or delete samples, undo history.

A move is accepted only when the group's wells match a grid slot of its strategy and none of
them is already used. Invalid moves raise EditError and change nothing.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

from .model import Layout, Record, Target, N_WELLS, well_position, is_edge_well
from .strategies import CapacityError, allowed_shapes, group_wells_for_start, place_records


class EditError(ValueError):
    """A manual edit that the strategy grid or the rules do not allow."""


def move_group(records: list, targets: list, layout: Layout, gid: str, start_well: int) -> Layout:
    """Place group `gid` so that its start (top-left) well is `start_well`. Returns a new Layout."""
    rec = next((r for r in records if r.gid == gid), None)
    if rec is None:
        raise EditError(f"{gid} is not in the sample table.")
    tindex = {t.assay_id: i for i, t in enumerate(targets)}
    if rec.target not in tindex:
        raise EditError(f"target {rec.target!r} is not in the targets table.")
    if not 1 <= start_well <= N_WELLS:
        raise EditError(f"well {start_well} is off the plate.")
    try:
        wells = group_wells_for_start(layout.strategy, start_well)
    except CapacityError as exc:
        raise EditError(str(exc)) from exc
    shapes = allowed_shapes(layout.strategy, len(targets), layout.edge_guard, tindex[rec.target])
    where = well_position(start_well)
    if frozenset(wells) not in shapes:
        if layout.edge_guard and any(is_edge_well(w) for w in wells):
            raise EditError(f"{where}: the edge guard keeps row P and column 24 empty.")
        raise EditError(f"{where} is not a valid {layout.strategy} start for this group. "
                        f"The triplicate would not match the grid.")
    for other_gid, other_wells in layout.assignments.items():
        if other_gid == gid:
            continue
        if set(other_wells) & set(wells):
            clash = other_gid
            raise EditError(f"{where}: those wells are already used by {clash}.")
    new = layout.copy()
    new.assignments[gid] = tuple(sorted(wells))
    return new


def clear_groups(layout: Layout, gids) -> Layout:
    """Take groups off the plate. Their sample rows stay, so export stays blocked until placed or deleted."""
    new = layout.copy()
    for gid in gids:
        new.assignments.pop(gid, None)
    return new


def add_record(records: list, targets: list, layout: Layout, rec: Record):
    """Append a record and place it in the first free grid position. Returns (records, layout)."""
    new_records = [r.copy() for r in records] + [rec]
    from .model import assign_gids
    assign_gids(new_records)
    new_layout = place_records(new_records, targets, layout)
    return new_records, new_layout


def delete_records(records: list, layout: Layout, gids) -> tuple:
    """Remove sample rows and their wells."""
    gids = set(gids)
    new_records = [r.copy() for r in records if r.gid not in gids]
    new_layout = clear_groups(layout, gids)
    return new_records, new_layout


@dataclass
class History:
    """Undo and redo for the last `limit` states. A state is (records, layout)."""

    limit: int = 20
    past: list = field(default_factory=list)
    future: list = field(default_factory=list)

    def snapshot(self, records: list, layout: Layout) -> None:
        """Call before changing state."""
        self.past.append((copy.deepcopy(records), layout.copy()))
        if len(self.past) > self.limit:
            self.past.pop(0)
        self.future.clear()

    def undo(self, records: list, layout: Layout):
        if not self.past:
            return records, layout
        self.future.append((copy.deepcopy(records), layout.copy()))
        records2, layout2 = self.past.pop()
        return records2, layout2

    def redo(self, records: list, layout: Layout):
        if not self.future:
            return records, layout
        self.past.append((copy.deepcopy(records), layout.copy()))
        records2, layout2 = self.future.pop()
        return records2, layout2

    def __len__(self) -> int:
        return len(self.past)
