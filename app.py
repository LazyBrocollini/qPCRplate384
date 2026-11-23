"""384 qPCR Plate Builder: Streamlit UI. All logic lives in the plate/ package.

Run with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from plate.design import DesignSpec, design_size, generate_design, read_samples
from plate.edit import EditError, History, add_record, clear_groups, delete_records, move_group
from plate.export_txt import ExportBlocked, build_bytes, created_stamp, export_filename, export_record, plate_map_csv
from plate.model import (DEFAULT_PASSIVE, DEFAULT_QUENCHER, DEFAULT_REPORTER, DEFAULT_TEMPLATE, N_WELLS,
                         MAX_GROUPS, PlateSettings, Layout, Record, Target, well_position, parse_position)
from plate.naming import sample_name
from plate.recipe import from_recipe, to_recipe
from plate.render import COLOR_BY, plate_pdf, plate_png
from plate.strategies import STRATEGY_NAMES, CapacityError, auto_place, recommend
from plate.validate import validate

st.set_page_config(page_title="384 qPCR Plate Builder", layout="wide")
TZ = ZoneInfo("America/Los_Angeles")
OPTIONS = ["Auto", "S1", "S2", "S3", "S4"]
SAMPLE_ROWS = list("ABCDEFGH")
SCHEMATIC = {
    "S1": "Each plate row = one condition; each block of 3 columns = one sample row (A to H).",
    "S2": "One 2x2 block per sample-target pair: Q1 Q2 / Q3 (Q4 empty). Up to 96 blocks.",
    "S3": "Vertical triplicates in rows A to O; row P = 8 control groups. One target only.",
    "S4": "Both targets for one sample side by side in one row (4 samples per row).",
}


def _init():
    ss = st.session_state
    if "records" not in ss:
        ss.records = []
        ss.targets = [Target("ACTN1_HTS5001", "ACTN1"), Target("ACTB_Hs01060665_g1", "ACTB")]
        ss.layout = Layout()
        ss.settings = PlateSettings()
        ss.history = History(limit=20)
        ss.strategy_choice = "Auto"
        ss.edge_guard = False
        ss.seed_on = False
        ss.seed = 1234
        ss.passive = DEFAULT_PASSIVE


def _commit(records, layout, settings=None):
    """Record the current state for undo, then store the new state."""
    st.session_state.history.snapshot(st.session_state.records, st.session_state.layout)
    st.session_state.records = records
    st.session_state.layout = layout
    if settings is not None:
        st.session_state.settings = settings


def _report():
    ss = st.session_state
    return validate(ss.records, ss.targets, ss.layout, ss.settings)


def sidebar():
    ss = st.session_state
    with st.sidebar:
        st.header("Layout")
        ss.strategy_choice = st.radio(
            "Strategy", OPTIONS, index=OPTIONS.index(ss.strategy_choice),
            format_func=lambda k: "Auto (recommend)" if k == "Auto" else STRATEGY_NAMES[k])
        if ss.strategy_choice in SCHEMATIC:
            st.caption(SCHEMATIC[ss.strategy_choice])
        ss.edge_guard = st.toggle("Edge guard (keep row P and column 24 empty)", value=ss.edge_guard)
        if ss.edge_guard != ss.layout.edge_guard:
            st.caption("Click Auto-place to apply the edge guard.")
        ss.seed_on = st.toggle("Shuffle within blocks", value=ss.seed_on,
                               help="Reduces plate-position bias. The seed is saved in the export record.")
        if ss.seed_on:
            ss.seed = int(st.number_input("Shuffle seed", value=int(ss.seed), step=1))

        st.header("Targets")
        tdf = pd.DataFrame([{"assay_id": t.assay_id, "alias": t.alias, "reporter": t.reporter,
                             "quencher": t.quencher} for t in ss.targets])
        edited = st.data_editor(tdf, num_rows="dynamic", hide_index=True, key="targets_editor")
        ss.targets = [Target(str(r.get("assay_id") or "").strip(), str(r.get("alias") or "").strip(),
                             str(r.get("reporter") or DEFAULT_REPORTER), str(r.get("quencher") or DEFAULT_QUENCHER),
                             ss.passive)
                      for _, r in edited.iterrows()]

        st.header("Instrument")
        ss.experiment = st.text_input("Experiment name (file name)", value=ss.settings.experiment)
        ss.settings.experiment = ss.experiment
        ss.passive = st.text_input("Passive reference", value=ss.passive)
        ss.settings.ntc_task = st.toggle("Label NTC wells Task = NTC", value=ss.settings.ntc_task,
                                         help="Enable only after confirming the instrument software supports NTC.")
        ss.settings.barcode = st.text_input("Barcode (optional)", value=ss.settings.barcode)
        style = st.radio("Name spaces", ["Spaces (default)", "Underscores"], index=0)
        ss.settings.name_style = "space" if style.startswith("Spaces") else "underscore"
        ss.settings.name_template = st.text_input("Name template", value=ss.settings.name_template or DEFAULT_TEMPLATE)


def top_bar():
    ss = st.session_state
    c1, c2, c3, c4 = st.columns([1, 1, 1, 5])
    if c1.button("Undo", disabled=not ss.history.past):
        ss.records, ss.layout = ss.history.undo(ss.records, ss.layout)
        st.rerun()
    if c2.button("Redo", disabled=not ss.history.future):
        ss.records, ss.layout = ss.history.redo(ss.records, ss.layout)
        st.rerun()
    rep = _report()
    used_groups = rep.groups_used
    cards = st.columns(5)
    cards[0].metric("Samples", rep.sample_count)
    cards[1].metric(f"Groups (of {MAX_GROUPS})", used_groups)
    cards[2].metric("Wells used", rep.wells_used)
    cards[3].metric("Empty wells", rep.empty_wells)
    cards[4].metric("Warnings", len(rep.warnings), delta=f"{len(rep.errors)} errors" if rep.errors else None,
                    delta_color="inverse")


def tab_samples():
    ss = st.session_state
    st.subheader("1. Samples")
    with st.expander("Generate design", expanded=not ss.records):
        c1, c2 = st.columns(2)
        rows = c1.multiselect("Sample rows", SAMPLE_ROWS, default=SAMPLE_ROWS)
        conds = c2.text_input("Condition levels (in plate-row order)", "1000nM, 100nM, 10nM, 1nM, 0.1nM, 0nM")
        conds = [c.strip() for c in conds.split(",") if c.strip()]
        dil_options = ["undiluted", "1to1", "1to2", "1to4"]
        default_dil = ["undiluted", "undiluted", "1to1", "1to1", "1to2", "1to2", "1to4", "1to4"]
        dil = []
        cols = st.columns(max(1, len(rows)))
        for i, r in enumerate(rows):
            dil.append(cols[i].selectbox(f"Row {r} dilution", dil_options,
                                         index=dil_options.index(default_dil[SAMPLE_ROWS.index(r)]), key=f"dil_{r}"))
        c3, c4, c5 = st.columns(3)
        aso = c3.text_input("Active ASO ID", "ILC_582465")
        ntc_sets = c4.selectbox("NTC sets", [0, 1, 2], index=2)
        targets = c5.multiselect("Targets", [t.assay_id for t in ss.targets if t.assay_id],
                                 default=[t.assay_id for t in ss.targets if t.assay_id])
        spec = DesignSpec(sample_rows=tuple(rows), conditions=tuple(conds), dilutions=tuple(dil), aso_id=aso,
                          target_ids=tuple(targets), ntc_sets=ntc_sets,
                          task_for_ntc="NTC" if ss.settings.ntc_task else "UNKNOWN")
        size = design_size(spec)
        st.info(f"Design: {size['sample_rows']} sample rows x {size['condition_levels']} condition levels x "
                f"{size['targets']} target(s) = {size['groups']} triplicate groups (capacity {MAX_GROUPS}).")
        if size["groups"] > MAX_GROUPS:
            st.error(f"{size['groups']} groups exceed the {MAX_GROUPS}-group plate capacity.")
        if st.button("Generate design (replaces samples)", type="primary", disabled=size["groups"] == 0):
            recs = generate_design(spec)
            ss.settings.expected_sample_rows = size["sample_rows"]
            ss.settings.expected_conditions = size["condition_levels"]
            ss.settings.expected_targets = size["targets"]
            _commit(recs, Layout(strategy="S1", edge_guard=False, seed=None))
            st.rerun()

    with st.expander("Upload or paste CSV, TSV, or XLSX"):
        st.caption("Columns: sample_row, condition, dilution, aso_id, target (optional: task, set). "
                   "Names are generated from these fields.")
        up = st.file_uploader("Sample file", type=["csv", "tsv", "xlsx"])
        if up is not None and st.button("Load file (replaces samples)"):
            recs, msgs = read_samples(up.getvalue(), up.name)
            for m in msgs:
                st.warning(m)
            if recs:
                ss.settings.expected_sample_rows = ss.settings.expected_conditions = None
                _commit(recs, Layout(strategy="S1", edge_guard=False))
                st.rerun()

    with st.expander("Add one sample"):
        c1, c2, c3, c4, c5 = st.columns(5)
        r = c1.selectbox("Sample row", SAMPLE_ROWS, key="m_row")
        cond = c2.text_input("Condition", "1000nM", key="m_cond")
        dl = c3.selectbox("Dilution", ["undiluted", "1to1", "1to2", "1to4"], key="m_dil")
        a = c4.text_input("ASO ID", "ILC_582465", key="m_aso")
        tgt = c5.selectbox("Target", [t.assay_id for t in ss.targets if t.assay_id] or [""], key="m_tgt")
        if st.button("Add sample"):
            new = Record(r, cond.replace(" ", ""), dl, a, tgt, "UNKNOWN", 1)
            try:
                recs, lay = add_record(ss.records, ss.targets, ss.layout, new)
                _commit(recs, lay)
                st.rerun()
            except CapacityError as exc:
                st.error(str(exc))

    if ss.records:
        st.caption(f"{len(ss.records)} sample-target groups. Names are generated from the fields.")
        st.dataframe(pd.DataFrame([{"group": r.gid, "target": r.target, "name": sample_name(r, ss.settings.name_style,
                                    ss.settings.name_template), "row": r.sample_row, "condition": r.condition,
                                    "dilution": r.dilution, "aso_id": r.aso_id} for r in ss.records]),
                     hide_index=True, use_container_width=True)


def tab_layout():
    ss = st.session_state
    st.subheader("2. Layout")
    c1, c2 = st.columns([1, 3])
    if c1.button("Auto-place", type="primary", disabled=not ss.records):
        strategy = ss.strategy_choice
        seed = ss.seed if ss.seed_on else None
        if strategy == "Auto":
            strategy, reason, lay = recommend(ss.records, ss.targets, ss.edge_guard, seed)
            st.caption(f"Recommended {strategy}: {reason}")
            if lay is None:
                st.error(reason)
                return
        else:
            try:
                lay = auto_place(ss.records, ss.targets, strategy, ss.edge_guard, seed)
            except CapacityError as exc:
                st.error(str(exc))
                return
        _commit(ss.records, lay)
        st.rerun()
    color_by = c2.radio("Color by", COLOR_BY, horizontal=True)
    rep = _report()
    if ss.layout.assignments:
        st.image(plate_png(ss.records, ss.targets, ss.layout, ss.settings, rep, color_by=color_by),
                 use_container_width=True)
    else:
        st.info("Place the samples to see the plate.")

    st.markdown("**Move, clear, or delete a group** (keyboard path: pick a group, then a start well)")
    gids = {r.gid: f"{r.gid}: {sample_name(r, ss.settings.name_style, ss.settings.name_template)} [{r.target}]"
            for r in ss.records}
    if gids:
        c1, c2, c3, c4 = st.columns([3, 2, 1, 1])
        gid = c1.selectbox("Group", list(gids), format_func=lambda g: gids[g])
        start = c2.selectbox("Start well", [well_position(w) for w in range(1, N_WELLS + 1)],
                             index=0, key="start_well")
        if c3.button("Move"):
            try:
                _commit(ss.records, move_group(ss.records, ss.targets, ss.layout, gid, parse_position(start)))
                st.rerun()
            except EditError as exc:
                st.error(str(exc))
        if c4.button("Clear group"):
            _commit(ss.records, clear_groups(ss.layout, [gid]))
            st.rerun()
        if st.button("Delete this sample row"):
            recs, lay = delete_records(ss.records, ss.layout, [gid])
            _commit(recs, lay)
            st.rerun()


def tab_export():
    ss = st.session_state
    st.subheader("3. Check and export")
    rep = _report()
    for i in rep.errors:
        st.error(i.message)
    for i in rep.warnings:
        st.warning(i.message)
    for i in rep.infos:
        st.info(i.message)
    if rep.completeness:
        st.markdown("**Sample completeness by target**")
        comp = pd.DataFrame.from_dict(rep.completeness, orient="index")
        st.dataframe(comp.replace({True: "yes", False: "missing"}), use_container_width=True)
    ack = True
    if rep.warnings:
        ack = st.checkbox("I have reviewed the warnings and want to export anyway")
    now = datetime.now(TZ)
    stamp = created_stamp(now)
    settings = ss.settings
    ok = rep.can_export and ack and bool(ss.records)
    if rep.errors:
        st.error("Export is blocked until the errors are fixed.")
    try:
        txt = build_bytes(ss.records, ss.targets, ss.layout, settings, created=stamp, report=rep) if ok else None
    except ExportBlocked as exc:
        st.error(str(exc))
        txt = None
    fname = export_filename(settings.experiment, now)
    c1, c2, c3, c4, c5 = st.columns(5)
    if txt is not None:
        c1.download_button("Instrument TXT", txt, file_name=fname, mime="text/plain")
    else:
        c1.button("Instrument TXT", disabled=True)
    c2.download_button("Plate map CSV", plate_map_csv(ss.records, ss.targets, ss.layout, settings).encode("utf-8"),
                       file_name=fname.replace(".txt", "_map.csv"), mime="text/csv", disabled=not ss.layout.assignments)
    c3.download_button("Plate PNG", plate_png(ss.records, ss.targets, ss.layout, settings, rep) if ss.layout.assignments else b"",
                       file_name=fname.replace(".txt", ".png"), mime="image/png", disabled=not ss.layout.assignments)
    c4.download_button("Plate PDF", plate_pdf(ss.records, ss.targets, ss.layout, settings, rep) if ss.layout.assignments else b"",
                       file_name=fname.replace(".txt", ".pdf"), mime="application/pdf", disabled=not ss.layout.assignments)
    c5.download_button("Layout recipe JSON", to_recipe(ss.records, ss.targets, ss.layout, settings),
                       file_name=fname.replace("_384well_import", "_recipe").replace(".txt", ".json"), mime="application/json")
    st.download_button("Export record JSON (includes shuffle seed)",
                       export_record(ss.records, ss.targets, ss.layout, settings, fname, stamp, rep, ack),
                       file_name=fname.replace(".txt", "_record.json"), mime="application/json", disabled=not ok)
    up = st.file_uploader("Reload a layout recipe", type=["json"], key="recipe_up")
    if up is not None and st.button("Load recipe"):
        try:
            recs, tgts, lay, sets = from_recipe(up.getvalue().decode("utf-8"))
            st.session_state.records, st.session_state.layout = recs, lay
            st.session_state.targets, st.session_state.settings = tgts, sets
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


_init()
st.title("384 qPCR Plate Builder")
sidebar()
top_bar()
t1, t2, t3 = st.tabs(["Samples", "Layout", "Check and export"])
with t1:
    tab_samples()
with t2:
    tab_layout()
with t3:
    tab_export()
