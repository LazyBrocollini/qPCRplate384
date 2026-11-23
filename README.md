# 384 qPCR Plate Builder

Lay out a 384-well qPCR plate in which every sample-target pair is a triplicate, check it, and export the instrument import TXT in the attached format (Windows-1252, CRLF).

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Tests (acceptance tests from the spec plus unit checks):

```bash
pytest -q                     # with pytest installed
python3 tests/run_tests.py    # without pytest
```

## Layout


| Path                  | Contents                                                                  |
| --------------------- | ------------------------------------------------------------------------- |
| `app.py`              | Streamlit UI only; calls the pure functions in `plate/`                   |
| `plate/model.py`      | Well math, targets, sample records, layouts, settings                     |
| `plate/strategies.py` | S1 to S4 placement, Auto recommendation, slot catalogs                    |
| `plate/validate.py`   | Hard errors (block export) and warnings (confirm to export)               |
| `plate/edit.py`       | Move, clear, add, delete, and the 20-step undo/redo history               |
| `plate/naming.py`     | Sample names from structured fields; character rules                      |
| `plate/design.py`     | Design generator; CSV, TSV, and XLSX import                               |
| `plate/export_txt.py` | Instrument TXT, parser for re-checking, plate map CSV                     |
| `plate/render.py`     | Plate map PNG and PDF (color by target, sample, condition, or dilution)   |
| `plate/recipe.py`     | JSON layout recipe (save and reload)                                      |
| `tests/`              | Acceptance and unit tests; `tests/fixtures/` holds the two attached files |


## Rules enforced

* 384 wells, row-major (A1, A24, B1, P24). A triplicate is 3 wells on the strategy grid. Capacity 128 groups.
* Export is blocked by: a group without 3 contiguous grid wells, a well used twice, more than 128 groups, a sample name with a tab, line break, or non-allowed character, a duplicate name within a target, or a target with no assay ID.
* Warnings need confirmation: no NTC, no 0 nM or no-ASO control, incomplete sample-by-target sets, gaps inside used blocks, unused capacity, and counts that differ from the design.
* Empty wells always export (all 384 rows), with only Well and Well Position filled.
* NTC wells export `Task = UNKNOWN` unless the NTC task setting is on.

## Verified

* The attached reference plate (S1, 2 targets, 8 sample rows x 8 condition levels) reproduces byte-for-byte.
* The attached partial plate (21 wells) reproduces byte-for-byte when rebuilt from its own parsed fields.
* Export re-parses, and each well's sample and target match the layout.

## Known gaps

* **Drag and drop is not implemented.** The plate view is a static PNG. The keyboard path works: pick a group, pick a start well, click Move. A custom HTML5 drag component is the next step.
* **Hover details are not implemented.** Plotly is listed in requirements but not used.
* **Edge guard is a hard rule.** With it on, S1 cannot hold sample row H (columns 22 to 24 include column 24), so Auto skips S1 and S2 is used. Confirm this is the intended behavior.
* Shuffle order is seeded. The seed is saved in the layout recipe and in the export record JSON.
* Auto recommends the first strategy that fits (S1, then S2, S3, S4). It does not yet weigh the "best for" notes.
* The `Date Created` day uses a zero-padded day (`May 03`). Check this against the instrument software for single-digit days.
* XLSX import is implemented but not tested in this environment. CSV and TSV are tested.
* Recipes are downloaded, not saved to a folder.

