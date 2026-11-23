"""Instrument import TXT (Windows-1252, CRLF), plate map CSV, and the export record.

The TXT layout matches the attached reference file byte for byte:
  - 4 preamble lines (each has 12 tab-separated fields, i.e. 11 trailing tabs), a blank line,
    '[Sample Setup]', and the 12-column header (no trailing tab).
  - 384 data rows in well order. Empty wells keep only Well and Well Position.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from typing import Optional

from .model import (N_WELLS, PlateSettings, Layout, Record, Target, well_position, MAX_GROUPS)
from .naming import sample_name
from .validate import validate

HEADER = ["Well", "Well Position", "Sample Name", "Sample Color", "Biogroup Name", "Biogroup Color",
          "Target Name", "Target Color", "Task", "Reporter", "Quencher", "Quantity"]
CRLF = "\r\n"
ENCODING = "cp1252"


class ExportBlocked(ValueError):
    """Export refused because the layout has hard errors."""

    def __init__(self, report):
        self.report = report
        msgs = "; ".join(i.message for i in report.errors[:5])
        super().__init__(f"Export blocked by {len(report.errors)} error(s): {msgs}")


def created_stamp(when: datetime) -> str:
    """'Wed May 13 15:00:41 PDT 2026' style (the instrument's Date Created line)."""
    tz = when.tzname() or ""
    return f"{when:%a %b %d %H:%M:%S} {tz} {when:%Y}"


def export_filename(experiment: str, when: datetime) -> str:
    base = re.sub(r"[^A-Za-z0-9_.\-]+", "_", (experiment or "").strip()).strip("_.") or "experiment"
    return f"{base}_384well_import_{when:%Y%m%d}.txt"


def _tabbed(text: str) -> str:
    """A preamble-style line: one field followed by 11 empty fields (12 fields total)."""
    return "\t".join([text] + [""] * 11)


def _data_fields(well: int, rec: Optional[Record], target: Optional[Target], settings: PlateSettings) -> list:
    pos = well_position(well)
    if rec is None:
        return [str(well), pos] + [""] * 10
    name = sample_name(rec, settings.name_style, settings.name_template)
    biogroup = "NTC" if rec.is_ntc else name
    task = "NTC" if (settings.ntc_task and rec.task == "NTC") else "UNKNOWN"
    return [str(well), pos, name, "", biogroup, "", target.assay_id, "", task,
            target.reporter, target.quencher, ""]


def well_owner_map(records: list, layout: Layout) -> dict:
    """well -> (record, target-less placeholder handled by caller). Returns well -> gid."""
    owner = {}
    for gid, wells in layout.assignments.items():
        for w in wells:
            owner[w] = gid
    return owner


def build_txt(records: list, targets: list, layout: Layout, settings: Optional[PlateSettings] = None,
              created: Optional[str] = None, barcode: Optional[str] = None, report=None) -> str:
    """Return the full instrument file as a Python str (CRLF line endings). Raises ExportBlocked."""
    settings = settings or PlateSettings()
    report = report or validate(records, targets, layout, settings)
    if report.errors:
        raise ExportBlocked(report)
    if created is None:
        from zoneinfo import ZoneInfo
        created = created_stamp(datetime.now(ZoneInfo("America/Los_Angeles")))
    barcode = settings.barcode if barcode is None else barcode
    if any(ch in barcode for ch in "\t\r\n"):
        raise ValueError("barcode cannot contain tabs or line breaks")
    passive = targets[0].passive_reference if targets else "ROX"
    tgt = {t.assay_id: t for t in targets}
    by_gid = {r.gid: r for r in records}
    owner = well_owner_map(records, layout)

    lines = [
        _tabbed("* Block Type = 384-Well Block"),
        _tabbed(f"* Date Created = {created}"),
        _tabbed(f"* Passive Reference = {passive}"),
        _tabbed(f"* Barcode = {barcode}"),
        _tabbed(""),
        _tabbed("[Sample Setup]"),
        "\t".join(HEADER),
    ]
    for well in range(1, N_WELLS + 1):
        gid = owner.get(well)
        rec = by_gid.get(gid) if gid else None
        target = tgt.get(rec.target) if rec else None
        lines.append("\t".join(_data_fields(well, rec, target, settings)))
    return CRLF.join(lines) + CRLF


def build_bytes(*args, **kwargs) -> bytes:
    """build_txt encoded as Windows-1252."""
    return build_txt(*args, **kwargs).encode(ENCODING)


def parse_txt(data) -> dict:
    """Parse an import file (bytes or str). Returns {'preamble': {...}, 'rows': [dict, ...]}."""
    text = data.decode(ENCODING) if isinstance(data, bytes) else data
    if not text.endswith(CRLF):
        raise ValueError("file must end with CRLF")
    lines = text.split(CRLF)[:-1]
    if len(lines) != 7 + N_WELLS:
        raise ValueError(f"expected {7 + N_WELLS} lines, found {len(lines)}")
    preamble = {}
    for line in lines[:4]:
        fields = line.split("\t")
        if len(fields) != 12:
            raise ValueError("preamble line does not have 12 fields")
        key, _, value = fields[0].partition(" = ")
        preamble[key.lstrip("* ").strip()] = value
    if lines[5] != _tabbed("[Sample Setup]"):
        raise ValueError("missing [Sample Setup] line")
    if lines[6].split("\t") != HEADER:
        raise ValueError("header does not match the import format")
    rows = []
    for i, line in enumerate(lines[7:], start=1):
        f = line.split("\t")
        if len(f) != 12:
            raise ValueError(f"data row {i} has {len(f)} fields")
        rows.append({"well": int(f[0]), "position": f[1], "sample": f[2], "biogroup": f[4],
                     "target": f[6], "task": f[8], "reporter": f[9], "quencher": f[10],
                     "quantity": f[11], "info_colors": (f[3], f[5], f[7])})
        if rows[-1]["well"] != i or rows[-1]["position"] != well_position(i):
            raise ValueError(f"row {i} is out of well order")
    return {"preamble": preamble, "rows": rows}


def plate_map_csv(records: list, targets: list, layout: Layout, settings: Optional[PlateSettings] = None) -> str:
    settings = settings or PlateSettings()
    tgt = {t.assay_id: t for t in targets}
    by_gid = {r.gid: r for r in records}
    owner = well_owner_map(records, layout)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["well", "well_position", "sample", "target", "condition", "dilution", "group_id", "replicate"])
    for well in range(1, N_WELLS + 1):
        gid = owner.get(well)
        if gid is None:
            w.writerow([well, well_position(well), "", "", "", "", "", ""])
            continue
        rec = by_gid[gid]
        wells = sorted(layout.assignments[gid])
        w.writerow([well, well_position(well), sample_name(rec, settings.name_style, settings.name_template),
                    tgt[rec.target].assay_id, rec.condition, rec.dilution, gid, wells.index(well) + 1])
    return buf.getvalue()


def export_record(records: list, targets: list, layout: Layout, settings: PlateSettings, filename: str,
                  created: str, report, acknowledged_warnings: bool) -> str:
    """JSON record of what was exported, including the random seed used for layout."""
    data = {
        "file": filename,
        "created": created,
        "experiment": settings.experiment,
        "strategy": layout.strategy,
        "edge_guard": layout.edge_guard,
        "seed": layout.seed,
        "ntc_task": settings.ntc_task,
        "name_style": settings.name_style,
        "name_template": settings.name_template,
        "passive_reference": targets[0].passive_reference if targets else "ROX",
        "groups": len(layout.assignments),
        "wells_used": report.wells_used,
        "errors": len(report.errors),
        "warnings": [w.code for w in report.warnings],
        "warnings_acknowledged": bool(acknowledged_warnings),
    }
    return json.dumps(data, indent=2)
