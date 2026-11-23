"""Validation of a layout. Hard errors block export; warnings need explicit confirmation.

Errors (block export): a pair with no wells or not exactly 3 wells, non-contiguous wells, a well
used twice, a group that does not match the strategy grid, more than 128 groups, a bad sample
name (tab, line break, or other characters), a duplicate name within a target, a target with no
assay ID, and an invalid field value.

Warnings (export allowed after confirmation): missing NTC or control per target, a sample present
for one target but not another, empty groups inside used blocks, unused capacity, and sample or
condition counts that differ from the design the user set.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .model import (GROUP_SIZE, MAX_GROUPS, N_WELLS, PlateSettings, Layout, Record, Target,
                    well_position, well_row_col, is_edge_well, N_ROWS)
from .naming import field_problems, name_problems, sample_name, TOKEN_RE
from .strategies import allowed_shapes, catalog


@dataclass(frozen=True)
class Issue:
    level: str                      # "error", "warning", or "info"
    code: str
    message: str
    gids: tuple = ()
    wells: tuple = ()


@dataclass
class Report:
    issues: list = field(default_factory=list)
    groups_used: int = 0
    wells_used: int = 0
    empty_wells: int = N_WELLS
    sample_count: int = 0
    capacity_full: int = 0
    capacity_active: int = 0
    completeness: dict = field(default_factory=dict)   # sample name -> {assay_id: bool}
    target_ids: list = field(default_factory=list)
    error_gids: set = field(default_factory=set)
    error_wells: set = field(default_factory=set)

    @property
    def errors(self) -> list:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def infos(self) -> list:
        return [i for i in self.issues if i.level == "info"]

    @property
    def can_export(self) -> bool:
        return not self.errors


def _connected(wells) -> bool:
    """True when the wells form one edge-connected group."""
    ws = list(wells)
    seen = {ws[0]}
    stack = [ws[0]]
    while stack:
        w = stack.pop()
        r, c = well_row_col(w)
        for other in ws:
            if other in seen:
                continue
            r2, c2 = well_row_col(other)
            if abs(r - r2) + abs(c - c2) == 1:
                seen.add(other)
                stack.append(other)
    return len(seen) == len(ws)


def _cond_label(rec: Record) -> str:
    return f"{rec.condition}" + (f" set {rec.set_index}" if rec.is_ntc else "")


def validate(records: list, targets: list, layout: Optional[Layout],
             settings: Optional[PlateSettings] = None) -> Report:
    settings = settings or PlateSettings()
    layout = layout or Layout()
    rep = Report(target_ids=[t.assay_id for t in targets])
    issues = rep.issues

    def err(code, msg, gids=(), wells=()):
        issues.append(Issue("error", code, msg, tuple(gids), tuple(wells)))
        rep.error_gids.update(gids)
        rep.error_wells.update(wells)

    def warn(code, msg, gids=(), wells=()):
        issues.append(Issue("warning", code, msg, tuple(gids), tuple(wells)))

    def info(code, msg):
        issues.append(Issue("info", code, msg))

    # ---- targets -------------------------------------------------------------
    ids = [t.assay_id for t in targets]
    if not targets:
        err("NO_TARGET", "Add at least one target.")
    for t in targets:
        if not (t.assay_id or "").strip():
            err("NO_ASSAY_ID", f"Target '{t.alias or '(unnamed)'}' has no assay ID.")
        elif not TOKEN_RE.fullmatch(t.assay_id):
            err("BAD_ASSAY_ID", f"Assay ID {t.assay_id!r} has characters not allowed "
                                "(use letters, digits, underscore, hyphen, period).")
    dupes = sorted({i for i in ids if ids.count(i) > 1 and i})
    for d in dupes:
        err("DUP_ASSAY_ID", f"Assay ID {d} appears more than once in the targets table.")
    if len({t.passive_reference for t in targets}) > 1:
        err("PASSIVE_MIXED", "Targets use different passive references. The instrument file "
                             "carries one passive reference per plate.")

    tindex = {t.assay_id: i for i, t in enumerate(targets)}
    rec_by_gid = {}

    # ---- records: fields, names, duplicates -----------------------------------
    names_seen = {}
    comp = {}
    for rec in records:
        label = rec.gid or "(no ID)"
        if rec.gid in rec_by_gid:
            err("DUP_GID", f"Group ID {rec.gid} is used by two sample rows.", (rec.gid,))
        rec_by_gid[rec.gid] = rec
        for p in field_problems(rec):
            err("BAD_FIELD", f"{label}: {p}.", (rec.gid,))
        if rec.target not in tindex:
            err("UNKNOWN_TARGET", f"{label}: target {rec.target!r} is not in the targets table.", (rec.gid,))
        try:
            name = sample_name(rec, settings.name_style, settings.name_template)
        except ValueError as exc:
            err("BAD_TEMPLATE", f"Name template problem: {exc}.")
            continue
        for p in name_problems(name):
            err("BAD_NAME", f"Sample name {name!r} {p}. Fix the sample fields.", (rec.gid,))
        key = (rec.target, name)
        if key in names_seen:
            err("DUP_NAME", f"Duplicate sample name {name!r} for target {rec.target} "
                            f"({names_seen[key]} and {rec.gid}).", (rec.gid, names_seen[key]))
        else:
            names_seen[key] = rec.gid
        comp.setdefault(name, {t: False for t in ids})
        if rec.target in comp[name]:
            comp[name][rec.target] = True

    rep.sample_count = len(comp)
    rep.completeness = comp

    if not records:
        warn("NO_SAMPLES", "No samples yet. Add a design, upload a file, or add samples one at a time.")

    # ---- layout: placement, size, contiguity, grid, overlaps -------------------
    for gid in layout.assignments:
        if gid not in rec_by_gid:
            err("STALE_GROUP", f"Layout has wells for {gid}, which is not in the sample table.", (gid,),
                layout.assignments[gid])
    unplaced = [r for r in records if r.gid not in layout.assignments]
    for rec in unplaced:
        err("UNPLACED", f"{rec.gid} ({rec.target}) has no wells. Place it or delete it.", (rec.gid,))

    strategy = layout.strategy
    n_targets = max(1, len(targets))
    if strategy == "S3" and len(targets) != 1:
        err("S3_TARGETS", "S3 is for one target. Choose S1, S2, or S4 for several targets.")

    well_owner = {}
    used_slots = set()
    groups_placed = 0
    if targets:
        for gid, wells in layout.assignments.items():
            rec = rec_by_gid.get(gid)
            if rec is None:
                continue
            groups_placed += 1
            label = f"{rec.gid} ({rec.target})"
            ws = tuple(sorted(wells))
            if len(ws) != GROUP_SIZE or len(set(ws)) != len(ws):
                err("GROUP_SIZE", f"{label} has {len(ws)} wells; a triplicate needs exactly 3.", (gid,), ws)
                continue
            if any(not 1 <= w <= N_WELLS for w in ws):
                err("WELL_RANGE", f"{label} uses a well outside 1 to {N_WELLS}.", (gid,), ws)
                continue
            if not _connected(ws):
                err("NOT_CONTIG", f"{label} wells are not one contiguous group.", (gid,), ws)
                continue
            for w in ws:
                if w in well_owner and well_owner[w] != gid:
                    err("WELL_TWICE", f"Well {well_position(w)} is used by {well_owner[w]} and {gid}.",
                        (gid, well_owner[w]), (w,))
                else:
                    well_owner[w] = gid
            ti = tindex.get(rec.target)
            shapes = allowed_shapes(strategy, n_targets, layout.edge_guard, ti)
            fs = frozenset(ws)
            if fs not in shapes:
                if layout.edge_guard and any(is_edge_well(w) for w in ws):
                    err("EDGE_GUARD", f"{label} uses an edge well (row P or column 24) while the edge guard is on.",
                        (gid,), ws)
                else:
                    err("OFF_GRID", f"{label} does not match a {strategy} grid slot "
                                    f"(it may straddle a block boundary).", (gid,), ws)
                continue
            used_slots.add(shapes[fs])

    if groups_placed > MAX_GROUPS:
        err("CAP_GROUPS", f"{groups_placed} triplicate groups are placed; the plate holds {MAX_GROUPS}.")
    if len(well_owner) > N_WELLS:
        err("CAP_WELLS", f"{len(well_owner)} wells are in use; the plate has {N_WELLS}.")

    # ---- counts and capacity -----------------------------------------------------
    rep.groups_used = groups_placed
    rep.wells_used = len(set(w for ws in layout.assignments.values() for w in ws))
    rep.empty_wells = N_WELLS - rep.wells_used
    if targets:
        full = catalog(strategy, n_targets, False)
        active = catalog(strategy, n_targets, layout.edge_guard)
        rep.capacity_full = len(full)
        rep.capacity_active = len(active)
        if layout.edge_guard and len(full) > len(active):
            info("EDGE_CAPACITY", f"Edge guard reduces {strategy} capacity from {len(full)} "
                                  f"to {len(active)} groups.")

        # gaps: empty slots inside containers (rows, columns, pairs) that hold a used slot
        used_containers = {s.container for s in used_slots}
        gap_slots = [s for s in active if s.container in used_containers and s not in used_slots]
        if gap_slots:
            warn("GAP", f"{len(gap_slots)} empty groups ({3 * len(gap_slots)} wells) sit inside used blocks. "
                         "Fill them, or confirm they are intentional.",
                 wells=tuple(w for s in gap_slots for w in s.wells))
        unused = len(active) - len(used_slots)
        if unused > 0:
            warn("UNUSED_CAPACITY", f"{unused} of {len(active)} group positions are unused "
                                    f"({3 * unused} wells).")

    # ---- per-target warnings ---------------------------------------------------
    for t in targets:
        mine = [r for r in records if r.target == t.assay_id]
        if not any(r.is_ntc for r in mine):
            warn("NO_NTC", f"Target {t.assay_id} has no NTC triplicate.")
        if not any(r.condition == "0nM" or r.aso_id == "ILC_none" for r in mine):
            warn("NO_CONTROL", f"Target {t.assay_id} has no 0 nM or no-ASO control.")

    incomplete = [n for n, flags in comp.items() if not all(flags.values())]
    if incomplete:
        warn("INCOMPLETE", f"{len(incomplete)} sample(s) are present for some targets but missing for others. "
                           "See the completeness matrix.")

    # ---- design size vs expectation -------------------------------------------
    if settings.expected_sample_rows is not None:
        found = len({r.sample_row for r in records})
        if found != settings.expected_sample_rows:
            warn("COUNT_ROWS", f"Design expects {settings.expected_sample_rows} sample rows; found {found}.")
    if settings.expected_conditions is not None:
        found = len({r.cond_key() for r in records})
        if found != settings.expected_conditions:
            warn("COUNT_CONDITIONS", f"Design expects {settings.expected_conditions} condition levels; found {found}.")
    if settings.expected_targets is not None and settings.expected_targets != len(targets):
        warn("COUNT_TARGETS", f"Design expects {settings.expected_targets} targets; found {len(targets)}.")

    # ---- instrument-setting consistency ----------------------------------------
    if not settings.ntc_task and any(r.is_ntc and r.task == "NTC" for r in records):
        warn("NTC_TASK_OFF", "Samples are labelled Task = NTC, but the NTC task setting is off. "
                             "The export will write UNKNOWN for these wells.")
    if strategy == "S3":
        for rec in records:
            if rec.is_control and rec.gid in layout.assignments and \
                    layout.assignments[rec.gid] and not all(well_row_col(w)[0] == N_ROWS - 1
                                                             for w in layout.assignments[rec.gid]):
                warn("CONTROL_ROW", f"{rec.gid} is a control but sits outside row P (the S3 control row).",
                     (rec.gid,))
                break
    return rep
