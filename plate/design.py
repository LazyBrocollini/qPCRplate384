"""Build sample records from a design form, or import them from CSV, TSV, or XLSX.

Design form: sample rows x condition levels x targets, with one dilution per sample row.
Each sample row is one triplicate column in S1 and one column of the attached layout. The
attached plate is 8 sample rows x (6 concentrations + NTC set 1 + NTC set 2) x 2 targets.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .model import DEFAULT_TEMPLATE, NTC, SAMPLE_ROWS, Record, assign_gids
from .naming import normalize_condition, normalize_dilution

COLUMNS = ("sample_row", "condition", "dilution", "aso_id", "target", "task", "set")
ALIASES = {
    "row": "sample_row", "sample row": "sample_row", "sample_row": "sample_row",
    "condition": "condition", "concentration": "condition", "conc": "condition",
    "dilution": "dilution",
    "aso": "aso_id", "aso_id": "aso_id", "aso id": "aso_id",
    "target": "target", "assay": "target", "assay id": "target", "assay_id": "target",
    "task": "task", "set": "set", "ntc set": "set",
}


@dataclass
class DesignSpec:
    sample_rows: tuple = SAMPLE_ROWS
    conditions: tuple = ("1000nM", "100nM", "10nM", "1nM", "0.1nM", "0nM")
    dilutions: Optional[tuple] = None       # one per sample row; default all undiluted
    aso_id: str = "ILC_582465"              # active ASO; 0 nM rows use ILC_none
    target_ids: tuple = ()
    ntc_sets: int = 2                       # 0, 1, or 2 NTC sets
    ntc_rows: Optional[tuple] = None        # sample rows that carry NTC (default all)
    task_for_ntc: str = "UNKNOWN"


def design_size(spec: DesignSpec) -> dict:
    """Expected numbers, shown before layout so mismatches are visible."""
    levels = len(spec.conditions) + spec.ntc_sets
    per_target = len(spec.sample_rows) * len(spec.conditions) + len(spec.ntc_rows or spec.sample_rows) * spec.ntc_sets
    return {
        "sample_rows": len(spec.sample_rows),
        "condition_levels": levels,
        "targets": len(spec.target_ids),
        "groups": per_target * len(spec.target_ids),
        "groups_per_target": per_target,
    }


def generate_design(spec: DesignSpec) -> list:
    """Build every sample-target record for the design. Order: target, condition level, sample row."""
    dil = list(spec.dilutions) if spec.dilutions else ["undiluted"] * len(spec.sample_rows)
    if len(dil) != len(spec.sample_rows):
        raise ValueError(f"need one dilution per sample row ({len(spec.sample_rows)}), got {len(dil)}")
    ntc_rows = spec.ntc_rows or spec.sample_rows
    records = []
    for target in spec.target_ids:
        for cond in spec.conditions:
            aso = "ILC_none" if normalize_condition(cond) == "0nM" else spec.aso_id
            for row, d in zip(spec.sample_rows, dil):
                records.append(Record(row, normalize_condition(cond), normalize_dilution(d), aso, target, "UNKNOWN", 1))
        for s in range(1, spec.ntc_sets + 1):
            for row in spec.sample_rows:
                if row not in ntc_rows:
                    continue
                records.append(Record(row, NTC, NTC, "", target, spec.task_for_ntc, s))
    return assign_gids(records)


def _column_map(columns) -> dict:
    out = {}
    for col in columns:
        key = str(col).strip().lower().replace("_", " ")
        key = ALIASES.get(key, ALIASES.get(key.replace(" ", "_"), None))
        if key:
            out[col] = key
    return out


def read_samples(data: bytes, filename: str) -> tuple:
    """Read sample rows from CSV, TSV, or XLSX. Returns (records, messages).

    Names are never read from the file. They are regenerated from the fields, so typing errors
    in names cannot reach the export. Unknown or missing columns are reported in messages.
    """
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        df = pd.read_excel(io.BytesIO(data), dtype=str).fillna("")
    else:
        text = data.decode("cp1252", errors="strict") if isinstance(data, bytes) else data
        sep = "\t" if name.endswith(".tsv") or text.count("\t") > text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, keep_default_na=False)
    return records_from_frame(df)


def records_from_frame(df: pd.DataFrame) -> tuple:
    messages = []
    cmap = _column_map(df.columns)
    needed = {"sample_row", "condition", "dilution", "aso_id", "target"}
    found = set(cmap.values())
    missing = sorted(needed - found)
    if missing:
        messages.append(f"Missing column(s): {', '.join(missing)}. Expected: sample_row, condition, dilution, aso_id, target.")
        return [], messages
    unknown = [c for c in df.columns if c not in cmap]
    if unknown:
        messages.append(f"Ignored column(s): {', '.join(str(c) for c in unknown)}. Sample names are generated, not read.")
    inv = {v: k for k, v in cmap.items()}
    recs = []
    for i, row in df.iterrows():
        vals = {k: str(row[inv[k]]).strip() for k in inv}
        if not any(vals.values()):
            continue
        cond = normalize_condition(vals.get("condition", ""))
        is_ntc = cond == NTC
        set_idx = 1
        if "set" in vals and vals["set"]:
            try:
                set_idx = int(float(vals["set"]))
            except ValueError:
                messages.append(f"Row {i + 2}: set {vals['set']!r} is not a number.")
        recs.append(Record(
            sample_row=vals.get("sample_row", "").upper(),
            condition=cond,
            dilution=NTC if is_ntc else normalize_dilution(vals.get("dilution", "")),
            aso_id="" if is_ntc else vals.get("aso_id", ""),
            target=vals.get("target", ""),
            task=(vals.get("task") or "UNKNOWN").upper() if vals.get("task") else "UNKNOWN",
            set_index=set_idx,
        ))
    return assign_gids(recs), messages
