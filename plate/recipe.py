"""JSON layout recipe: save and reload the full state so a layout can be edited later."""
from __future__ import annotations

import json
from dataclasses import asdict

from .model import Layout, PlateSettings, Record, Target

RECIPE_VERSION = 1


def to_recipe(records: list, targets: list, layout: Layout, settings: PlateSettings) -> str:
    data = {
        "version": RECIPE_VERSION,
        "settings": asdict(settings),
        "targets": [asdict(t) for t in targets],
        "records": [asdict(r) for r in records],
        "layout": layout.to_dict(),
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def from_recipe(text: str):
    """Return (records, targets, layout, settings). Raises ValueError on a bad recipe."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"recipe is not valid JSON: {exc}") from exc
    if data.get("version") != RECIPE_VERSION:
        raise ValueError(f"unsupported recipe version {data.get('version')!r}")
    targets = [Target(**t) for t in data["targets"]]
    records = [Record(**r) for r in data["records"]]
    layout = Layout.from_dict(data["layout"])
    settings = PlateSettings(**data["settings"])
    return records, targets, layout, settings
