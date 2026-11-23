"""Sample name generation from structured fields, plus field and name validation.

Default template: {sample_row}_row_{condition}_{dilution} {aso_id}
NTC names follow {sample_row}_row_NTC_NTC_NTC, with a _2 suffix for the second NTC set.
"""
from __future__ import annotations

import re
import string

from .model import DEFAULT_TEMPLATE, DILUTIONS, NTC, SAMPLE_ROWS, TASKS, Record

TEMPLATE_FIELDS = ("sample_row", "condition", "dilution", "aso_id")
NAME_RE = re.compile(r"[A-Za-z0-9 _.\-]+")        # the only characters an export name may use
TOKEN_RE = re.compile(r"[A-Za-z0-9_.\-]+")         # assay IDs and ASO IDs (no spaces)
CONDITION_RE = re.compile(r"(\d+(?:\.\d+)?)nM")
_DILUTION_ALIASES = {"1:1": "1to1", "1 to 1": "1to1", "1:2": "1to2", "1 to 2": "1to2",
                     "1:4": "1to4", "1 to 4": "1to4", "undil": "undiluted", "neat": "undiluted"}


def normalize_condition(text) -> str:
    """'1000 nM' -> '1000nM', '0.1 nm' -> '0.1nM', 'ntc' -> 'NTC'."""
    s = re.sub(r"\s+", "", str(text or "")).strip()
    if s.upper() == NTC:
        return NTC
    m = re.fullmatch(r"(\d+(?:\.\d+)?)nm", s, flags=re.IGNORECASE)
    if m:
        return f"{m.group(1)}nM"
    return s


def normalize_dilution(text) -> str:
    s = str(text or "").strip()
    low = s.lower()
    if low in _DILUTION_ALIASES:
        return _DILUTION_ALIASES[low]
    if low.replace(" ", "") in DILUTIONS:
        return low.replace(" ", "")
    if low.upper() == NTC:
        return NTC
    return s


def validate_template(template: str) -> list:
    """Return problems with a name template (empty list when it is valid)."""
    problems = []
    try:
        fields = [f for _, f, _, _ in string.Formatter().parse(template) if f is not None]
    except ValueError as exc:
        return [f"template is malformed: {exc}"]
    for f in fields:
        if f not in TEMPLATE_FIELDS:
            problems.append(f"unknown placeholder {{{f}}}")
    if "{sample_row}" not in template and "{sample_row" not in template:
        problems.append("template must include {sample_row}")
    return problems


def sample_name(rec: Record, style: str = "space", template: str = DEFAULT_TEMPLATE) -> str:
    """Generate the export sample name for a record from its structured fields."""
    if rec.is_ntc:
        name = f"{rec.sample_row}_row_NTC_NTC_NTC"
        if rec.set_index > 1:
            name += f"_{rec.set_index}"
    else:
        bad = validate_template(template)
        if bad:
            raise ValueError("; ".join(bad))
        name = template.format(sample_row=rec.sample_row, condition=rec.condition,
                               dilution=rec.dilution, aso_id=rec.aso_id)
    if style == "underscore":
        name = name.replace(" ", "_")
    return name


def name_problems(name: str) -> list:
    """Problems that would make a sample name unsafe for the instrument file."""
    problems = []
    if "\t" in name or "\n" in name or "\r" in name:
        problems.append("contains a tab or line break")
    elif not NAME_RE.fullmatch(name):
        bad = sorted({ch for ch in name if not NAME_RE.fullmatch(ch)})
        problems.append("contains characters not allowed: " + " ".join(repr(c) for c in bad))
    if name != name.strip():
        problems.append("has leading or trailing spaces")
    return problems


def field_problems(rec: Record) -> list:
    """Problems with the structured fields of one record (empty list when valid)."""
    problems = []
    if rec.sample_row not in SAMPLE_ROWS:
        problems.append(f"sample_row must be A to H, got {rec.sample_row!r}")
    if not rec.target:
        problems.append("target (assay ID) is empty")
    if rec.task not in TASKS:
        problems.append(f"task must be UNKNOWN or NTC, got {rec.task!r}")
    if not isinstance(rec.set_index, int) or rec.set_index < 1:
        problems.append("set must be 1 or higher")
    if rec.is_ntc:
        if rec.set_index > 2:
            problems.append("only two NTC sets are supported")
        if rec.dilution not in ("", NTC):
            problems.append("NTC rows use dilution NTC")
        if rec.aso_id not in ("", NTC):
            problems.append("NTC rows take no ASO ID")
    else:
        if not CONDITION_RE.fullmatch(rec.condition):
            problems.append(f"condition must look like 1000nM or 0.1nM or NTC, got {rec.condition!r}")
        if rec.dilution not in DILUTIONS:
            problems.append(f"dilution must be one of {', '.join(DILUTIONS)}, got {rec.dilution!r}")
        if not rec.aso_id:
            problems.append("aso_id is empty")
        elif not TOKEN_RE.fullmatch(rec.aso_id):
            problems.append(f"aso_id has characters not allowed: {rec.aso_id!r}")
        if rec.set_index != 1:
            problems.append("set applies to NTC rows only")
    return problems
