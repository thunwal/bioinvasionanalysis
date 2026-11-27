# Changes

Plain-language log of the `refactor` branch, phase by phase. "Results" says whether analysis results change compared
with the published version (details and numbers in [tests/REFERENCE.md](tests/REFERENCE.md)).

## Phase 0: safety
- Full backup of the repository and the report worktree: `~/backup_bioinvasionanalysis_20261127/`.
- Unfinished animation work committed on branch `animation`; branch `refactor` created from it, with branch `report`
  merged in. `main` is unchanged.
- Personal one-off scripts (neovelutina WFS download, Excel import) moved to `~/Git/bioinvasion-personal`.

## Phase 1: regression test against the paper
- `tests/test_regression.py` runs the current code on the input data of the paper (*M. sculpturalis*) and compares
  its results with the result files published with the paper, which the old code produced at the time. The old code
  itself is not run. Paths and populations are reproduced exactly.
- **Found and fixed: expansion rates did not follow the paper's methods.** The code regressed every observation with a
  running maximum whose value depended on the order of the rows within a year, so results changed with the file order
  and the pandas version (up to 7 km/year). Now one cumulative maximum per year is regressed, as the methods describe.
  Results: **yes**, e.g. Italy 2009 58.6 → 67.2 km/year (REFERENCE.md, difference 2).
- **Robust populations**: the sensitivity test used "median ≥ definition", everything else (and the paper) "median > definition".
  Now one helper, `is_robust()`, applies `>` everywhere. Results: only the sensitivity test, in 1.6 % of its rows
  (REFERENCE.md, difference 3).

## Phases 2–3: project folders, CLI, package
- **`params.py` and `main.py` are replaced** by one `project.toml` per project folder and `cli.py`
  (`init`, `import`, `paths`, `sensitivity`, `delineate`, `report`). Outputs go into the project folder, into subfolders
  named after the settings that produced them. Each stage writes a `manifest.json` and is skipped when nothing has
  changed, so trying another threshold reuses the least-cost paths.
- **Thresholds are absolute accumulated costs only**; the quantile is reported next to them.
- **Strict input checks**: CSV (comma or semicolon) or GeoPackage with fixed column names; invalid files are rejected
  with the reason and the affected rows. iNaturalist import with the options research grade / obscured / accuracy.
- **Sensitivity test**: an overview over all thresholds, then a high-resolution run over a suggested range. The rule behind
  the suggestion is printed and stored; the range can be set by hand.
- **Code**: the computations (`bioinvasion/core`) no longer read or write files; `bioinvasion/pipeline.py` does all
  file handling. Population grouping and thinning were rewritten to be fast (grouping 30× faster); the test confirms
  identical results.
- Removed: `report.py` (now `cli.py report`), the results explorer notebook (to be replaced by the web app), and
  the old demo outputs. The animation moved to the personal repository. The demo notebook works again.
- Results: no further changes.

## Phase 4: year maps and export
- `cli.py yearmaps`: one PNG per year end in the style of the population map of the paper (robust populations
  coloured, the same colour in every year), without title or source credits; the year is the file name.
- `cli.py export`: report, year maps, populations, expansion rates, sensitivity tests and manifests in one zip file, with a
  `settings.txt` that states all settings and numbers in words (for the methods section).
- Results: no changes.

## Phase 5: web app
- `python -m webapp` starts a Dash app with four pages: **1 Cost surface** (demo or upload, checked), **2 Observations**
  (CSV/GeoPackage upload with the same strict checks, or iNaturalist download; map and observations per year; then
  "Compute" runs paths and the sensitivity test with a progress bar), **3 Thresholds** (overview and high-resolution
  sensitivity test with the
  suggested range and its rule, stable ranges; you set the threshold and robust definition and see the populations
  on a map, the population table and the plain-language checks), **4 Export** (zip as in the CLI, plus `project.toml`).
- No animation in the web app; it stays a personal script.
- Limits for the public server: 2 million raster cells, 20,000 observations, 50 MB uploads, two computations at a
  time, sessions deleted after 24 hours.
- Tested end to end in a headless browser (`tests/e2e_webapp.py`), with the development server and with gunicorn.
- Results: no changes.

## Phase 6: deployment
- `Dockerfile` for the web app (Python 3.13, gunicorn on port 7860, demo cost surface and country borders included)
  and `docs/deployment.md` with the steps for a free Hugging Face Space or any Docker host.
- `requirements.txt` now holds what the app and the analysis need; `requirements-dev.txt` adds tests and the notebook.
- Manifests record the package version when git is not available (e.g. in the Docker image).
- The image was built and tested locally: the whole browser flow works in the container, and all tests (including
  the full sensitivity test of the paper) pass inside it. The slim base image needed `libexpat1` for rasterio.
- Manifest timestamps include the time zone (the container runs on UTC).
- Not yet done: deploying the Space (needs your Hugging Face account, see docs/deployment.md).

## Phase 7: wording, demo data, documentation
- "Sweep" is now called **sensitivity test** everywhere: command `python cli.py sensitivity`, settings section
  `[sensitivity]` in `project.toml`, files `sensitivity_coarse.csv` and `sensitivity__<from>-<to>x<step>.csv`.
  Existing project folders need `[sweep]` renamed to `[sensitivity]`; their old sweep files are not read any more.
- No demo observations any more (the *Isodontia mexicana* data are removed); the demo notebook downloads
  *M. sculpturalis* from iNaturalist instead. The tests use invented observations (`tests/synthetic.py`).
- Demo cost surface: the GTOPO30 surface with costs from 1 to 10 (1 + 9 × the former 0–1 surface) replaces the 0–1
  surface, in the web app, the notebook and the Docker image.
- README rewritten for users; maintainer information moved to `docs/maintainer.md`.
- Results: no changes (the regression test does not use the demo data).
