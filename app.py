"""Streamlit app: build unique well names from 96-well CSV tables.

Run with:  streamlit run app.py
"""

import pandas as pd
import streamlit as st

from plate_names import COLS, ROWS, build_records, count_repeats, parse_tables

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
