"""Streamlit app: build unique well names from 96-well CSV tables.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from layouts import LAYOUTS, ROWS_384, COLS_384, layout_by_key, place_on_384, wells_per_sample
from plate_names import COLS, ROWS, build_records, count_repeats, parse_tables

NO_LAYOUT = "none"

st.set_page_config(page_title="96-Well Name Builder", layout="wide")
st.title("96-well name builder")
st.caption(
    "For each well, the values from the selected tables are joined with "
    "underscores. Repeated names get _1, _2, _3, ... (the first occurrence "
    "keeps its plain name)."
)

uploads = st.file_uploader(
    "Upload 96-well CSV tables (one plate per file)",
    type=["csv"],
    accept_multiple_files=True,
)

if not uploads:
    st.info("Upload one or more CSV files to begin.")
    st.stop()

# Parse every upload. Each file is one plate with one or more 8 x 12 tables.
parsed = []
for up in uploads:
    tables = parse_tables(up.getvalue())
    if tables:
        parsed.append((up.name, tables))
    else:
        st.warning(f"No 8 x 12 table (rows A-H) found in {up.name}. Skipped.")

if not parsed:
    st.stop()

# Table titles across all files, in order of first appearance.
all_titles: list[str] = []
for _, tables in parsed:
    for t in tables:
        if t.title not in all_titles:
            all_titles.append(t.title)
titles_with_data = {t.title for _, tables in parsed for t in tables if t.has_data}

with st.sidebar:
    st.header("Tables to combine")
    selected = st.multiselect(
        "Tables included in each name",
        options=all_titles,
        default=[t for t in all_titles if t in titles_with_data],
        help=(
            "Tables are joined in the order they appear in the file, not the "
            "order you click them. Empty tables are skipped automatically."
        ),
    )

with st.expander("Detected tables", expanded=False):
    rows = []
    for fname, tables in parsed:
        for t in tables:
            filled = sum(1 for v in t.values.values() if v)
            rows.append({"File": fname, "Table": t.title, "Filled wells": filled})
    st.dataframe(pd.DataFrame(rows), hide_index=True)

if not selected:
    st.warning("Select at least one table in the sidebar.")
    st.stop()

records = build_records(parsed, set(selected))

if not records:
    st.warning("The selected tables have no values, so there are no names to build.")
    st.stop()

repeats = count_repeats([r["combined"] for r in records])
unique_count = len({r["unique"] for r in records})

c1, c2, c3 = st.columns(3)
c1.metric("Named wells", len(records))
c2.metric("Repeated names suffixed", repeats)
c3.metric("Unique names", unique_count)

st.subheader("Plate view (unique names)")
for fname, _ in parsed:
    grid = pd.DataFrame("", index=ROWS, columns=[str(c) for c in COLS])
    for rec in records:
        if rec["file"] == fname:
            row, col = rec["well"][0], rec["well"][1:]
            grid.loc[row, col] = rec["unique"]
    with st.expander(fname, expanded=len(parsed) == 1):
        st.dataframe(grid)

st.subheader("All wells")
long_df = pd.DataFrame(records).rename(
    columns={
        "file": "File",
        "well": "Well",
        "combined": "Combined name",
        "unique": "Unique name",
    }
)
long_df["Renamed"] = long_df["Combined name"] != long_df["Unique name"]
st.dataframe(long_df, hide_index=True)

st.download_button(
    "Download unique names (CSV)",
    data=long_df.to_csv(index=False).encode("utf-8"),
    file_name="well_names_unique.csv",
    mime="text/csv",
)

# ---------------------------------------------------------------------------
# Step 2: optional 384-well layout
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Step 2: Choose a 384-well layout (optional)")

layout_keys = [NO_LAYOUT] + [layout["key"] for layout in LAYOUTS]
layout_key = st.selectbox(
    "Layout",
    options=layout_keys,
    format_func=lambda k: "No layout (keep the 96-well names)"
    if k == NO_LAYOUT
    else layout_by_key(k)["name"],
)

if layout_key == NO_LAYOUT:
    st.info("Pick a layout to place the named samples into a 384-well plate.")
    st.stop()

layout = layout_by_key(layout_key)
st.caption(layout["description"] + " Quadrants follow the sheet's 384 quadrant key.")

copies = wells_per_sample(layout)
copy_text = ", ".join(
    f"{n} wells x {samples} samples" for n, samples in sorted(copies.items())
)
st.caption(f"Wells per sample in this layout: {copy_text}.")

make_unique_384 = st.checkbox(
    "Make repeated well names unique (_1, _2, ...)",
    value=True,
    help="Triplicate wells that share a sample name get _1, _2, ... after the first one, as in step 1.",
)

placed, missing = place_on_384(records, layout_key, unique_repeats=make_unique_384)

if missing:
    names_missing = ", ".join(m["sample"] for m in missing[:12])
    more = f" and {len(missing) - 12} more" if len(missing) > 12 else ""
    st.warning(
        f"{len(missing)} named sample(s) are not on this layout, so they are not "
        f"placed: {names_missing}{more}."
    )

if not placed:
    st.warning("None of your named samples fall on this layout.")
    st.stop()

st.metric("Wells filled on 384 plate", len(placed))

st.markdown("**384-well view (names on the plate)**")
for fname, _ in parsed:
    file_placed = [p for p in placed if p["file"] == fname]
    if not file_placed:
        continue
    grid384 = pd.DataFrame("", index=ROWS_384, columns=[str(c) for c in COLS_384])
    for p in file_placed:
        grid384.loc[p["well384"][0], p["well384"][1:]] = p["name"]
    with st.expander(fname, expanded=len(parsed) == 1):
        st.dataframe(grid384)

long_384 = pd.DataFrame(placed).rename(
    columns={
        "file": "File",
        "well384": "384 well",
        "quadrant": "Quadrant",
        "source": "Source 96 well",
        "sample": "Sample name",
        "name": "384 name",
    }
)
st.dataframe(long_384, hide_index=True)

st.download_button(
    "Download 384-well layout (CSV)",
    data=long_384.to_csv(index=False).encode("utf-8"),
    file_name=f"plate_384_{layout_key}.csv",
    mime="text/csv",
)
