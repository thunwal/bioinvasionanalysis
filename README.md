# bioinvasionanalysis

## About this project

Understanding how non-native species spread across landscapes is crucial for effective management strategies. 
This Python project aims to support the analysis of the **expansion dynamics of non-native species** by employing a 
data-driven, spatio-temporal approach. Using observation data and a landscape model ("cost surface"),

1. **sequential least-cost modelling** is applied in annual time steps to reconstruct the spread as least-cost paths, 
2. **distinct populations** are delineated by excluding paths with high accumulated cost, and 
3. **expansion rates** are calculated for all delineated populations using the distance regression method.

Version 1.1.0 of this repository was published as part of:

> Rohrbach, C., Wallentin, G., Bila Dubaić, J., & Lanner, J. (2025).
> Leveraging sequential least-cost modelling to uncover multiple introductions:
> a case study of an invasive wild bee species. *Landscape Ecology*, 40(8). 
> [https://doi.org/10.1007/s10980-025-02188-9](https://doi.org/10.1007/s10980-025-02188-9)

## Overview

The analysis runs in stages on a **project folder**, which holds a `project.toml` with all settings and receives all
results. The same code is used by the command line (`cli.py`), the [demo notebook](notebooks/bioinvasionanalysis_demo.ipynb)
and the web app.

| Stage | What happens | Output in the project folder |
|---|---|---|
| 1 import | observations are read and checked (CSV, GeoPackage or iNaturalist) | `presence/` |
| 2 paths | observations on NoData cells are removed, the earliest observation per cost surface cell is kept, and each observation is connected to the nearest earlier one by a least-cost path | `paths__<cost>__<years>/paths.gpkg` |
| 3 sweep | sensitivity analysis: overview over all thresholds, then a high-resolution sweep over a suggested range | `paths__.../sweep*.csv` |
| 4 delineate | populations for one accumulated cost threshold, expansion rates | `paths__.../delin__t<threshold>__r<robust>/` |
| 5 report | figures and tables of the paper, plain-language checks | `delin__.../report/` |

Every stage writes a `manifest.json` with its settings, the hashes of its input files and the code version, and is
skipped if nothing has changed. A new threshold therefore takes seconds: the least-cost paths are reused.
See [docs/architecture.md](docs/architecture.md) for how the code is organised.

## Setup

```bash
git clone https://github.com/thunwal/bioinvasionanalysis.git
cd bioinvasionanalysis
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Quick start with the demo project

The demo project [examples/isodontia](examples/isodontia/project.toml) uses European observations of the
[Mexican grass-carrying wasp](https://en.wikipedia.org/wiki/Isodontia_mexicana) from GBIF
([source](https://doi.org/10.15468/dl.jm6bhs)) and a very basic
[cost surface](data/cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif) derived from the GTOPO30 DEM by USGS
([source](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-global-30-arc-second-elevation-gtopo30)).

```bash
python cli.py sweep examples/isodontia                     # import, paths, sensitivity sweep (about 2 min)
python cli.py report examples/isodontia --threshold 0.19   # populations, figures, tables, checks
```

Or open [notebooks/bioinvasionanalysis_demo.ipynb](notebooks/bioinvasionanalysis_demo.ipynb) (`jupyter notebook`).

## Your own project

1. `python cli.py init ~/projects/myspecies` writes a commented `project.toml` template.
2. Set the observations (`[data]`) and the cost surface (`[cost]`).
3. `python cli.py sweep ~/projects/myspecies` runs the analysis up to the sensitivity sweep. It prints the
   high-resolution range it chose, the rule it used, and the stable threshold ranges it found.
4. Choose the threshold yourself, typically at the beginning of a stable range, and run
   `python cli.py report ~/projects/myspecies --threshold <value>`. Try other values the same way; each gets its own
   `delin__...` folder. Put the final value into `[delineation] threshold`.

`python cli.py --help` lists all commands and options.

## Web app

The same analysis in the browser, in four steps (cost surface, observations, thresholds, export). Each browser session
gets a project folder of its own under `webapp_jobs/` (deleted after 24 hours), with a `project.toml` that also works
with `cli.py`.

```bash
python -m webapp          # then open http://127.0.0.1:8050
```

## Input data

Inputs that do not meet these requirements are rejected with an explanation; nothing is guessed or repaired.

- **Observations as CSV**: UTF-8 ("CSV UTF-8" in Excel), comma- or semicolon-separated (recognised automatically;
  with semicolons, decimal commas are accepted in the coordinates). Required columns: `longitude`, `latitude`
  (WGS84 decimal degrees) and `year` (integer). Optional: `location` (e.g. country; used to name populations,
  e.g. "France 2008"), `source`, `source_id`. Other columns are ignored.
- **Observations as GeoPackage**: one point layer (or name the layer with `layer = "..."`) with a defined coordinate
  reference system and a `year` column (integer); optional `location`, `source`, `source_id`.
- **Observations from iNaturalist**: set `source = "inaturalist"` and `taxon`. Observations within the extent of the
  cost surface are downloaded (about one request per second, so this may take minutes) and assigned the country they
  lie in (Natural Earth). Options: research grade only (default), include obscured coordinates (default: no),
  maximum positional accuracy (default: no limit).
- **Cost surface**: GeoTIFF in a projected coordinate reference system with square cells. The values are the cost of
  moving through a cell; NoData cells (e.g. sea) cannot be crossed, and observations on them are removed.

## Tests

`python -m pytest` checks the code against the published *Megachile sculpturalis* analysis and the input rules;
`python -m pytest -m slow` additionally runs the full sensitivity sweep of the paper. The reference data are read
from `../manuscript/data` (or `BIOINVASION_REFERENCE_DIR`). Intended differences to the published results are
documented in [tests/REFERENCE.md](tests/REFERENCE.md). Changes are listed in [CHANGES.md](CHANGES.md).
