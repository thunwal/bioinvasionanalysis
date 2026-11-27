# Changes

Plain-language log of the `refactor` branch, phase by phase. "Results" says whether analysis results change compared
with the published version (details and numbers in [tests/REFERENCE.md](tests/REFERENCE.md)).

## Phase 0: safety
- Full backup of the repository and the report worktree: `~/backup_bioinvasionanalysis_20261127/`.
- Unfinished animation work committed on branch `animation`; branch `refactor` created from it, with branch `report`
  merged in. `main` is unchanged.
- Personal one-off scripts (neovelutina WFS download, Excel import) moved to `~/Git/bioinvasion-personal`.

## Phase 1: regression test against the paper
- `tests/test_regression.py` runs the published *M. sculpturalis* analysis and compares all outputs with the paper.
  Paths and populations are reproduced exactly.
- **Found and fixed: expansion rates did not follow the paper's methods.** The code regressed every observation with a
  running maximum whose value depended on the order of the rows within a year, so results changed with the file order
  and the pandas version (up to 7 km/year). Now one cumulative maximum per year is regressed, as the methods describe.
  Results: **yes**, e.g. Italy 2009 58.6 → 67.2 km/year (REFERENCE.md, difference 2).
- **Robust populations**: the sweep used "median ≥ definition", everything else (and the paper) "median > definition".
  Now one helper, `is_robust()`, applies `>` everywhere. Results: only the sweep, in 1.6 % of its rows
  (REFERENCE.md, difference 3).

## Phases 2–3: project folders, CLI, package
- **`params.py` and `main.py` are replaced** by one `project.toml` per project folder and `cli.py`
  (`init`, `import`, `paths`, `sweep`, `delineate`, `report`). Outputs go into the project folder, into subfolders
  named after the settings that produced them. Each stage writes a `manifest.json` and is skipped when nothing has
  changed, so trying another threshold reuses the least-cost paths.
- **Thresholds are absolute accumulated costs only**; the quantile is reported next to them.
- **Strict input checks**: CSV (comma or semicolon) or GeoPackage with fixed column names; invalid files are rejected
  with the reason and the affected rows. iNaturalist import with the options research grade / obscured / accuracy.
- **Sweep**: an overview over all thresholds, then a high-resolution sweep over a suggested range. The rule behind
  the suggestion is printed and stored; the range can be set by hand.
- **Code**: the computations (`bioinvasion/core`) no longer read or write files; `bioinvasion/pipeline.py` does all
  file handling. Population grouping and thinning were rewritten to be fast (grouping 30× faster); the test confirms
  identical results.
- Removed: `report.py` (now `cli.py report`), the results explorer notebook (to be replaced by the web app), and
  the old demo outputs. The animation moved to the personal repository. The demo notebook works again and uses the
  demo project `examples/isodontia`.
- Results: no further changes.
