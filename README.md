# bioinvasionanalysis

Reconstructs how a non-native species spread from dated observations and a landscape model ("cost surface"),
separates **distinct populations** (e.g. independent introductions), and calculates their **expansion rates**.

The method was published in:

> Rohrbach, C., Wallentin, G., Bila Dubaić, J., & Lanner, J. (2025).
> Leveraging sequential least-cost modelling to uncover multiple introductions:
> a case study of an invasive wild bee species. *Landscape Ecology*, 40(8).
> [https://doi.org/10.1007/s10980-025-02188-9](https://doi.org/10.1007/s10980-025-02188-9)

Please cite the paper if you use this tool. Version 1.1.0 of this repository is the code used in the paper.

<!-- Add the link to the public web app here after deployment (see docs/deployment.md). -->

## How it works

1. **Observations** are read and checked: one point per observation, with the year it was made.
2. **Least-cost paths**: observations on cells that cannot be crossed (NoData, e.g. sea) are removed, and only the
   earliest observation per cost surface cell is kept. Year by year, each observation is connected to the nearest
   observation of an earlier year by the path of least accumulated cost through the cost surface.
3. **Sensitivity test**: populations are delineated for many accumulated cost thresholds (first an overview over all
   thresholds, then a high-resolution run over a suggested range), and the resulting expansion rates are compared.
   Ranges of thresholds in which the rates hardly change ("stable ranges") are highlighted.
4. **Populations**: you choose the threshold. Paths with an accumulated cost at or above it are removed, as such
   connections are unlikely to result from spread through the landscape. Observations still connected by paths form
   one population. A population is **robust** if the median number of observations per year (years without
   observations count as 0) is above a set value (default 10); expansion rates are interpreted for robust
   populations only.
5. **Expansion rates** (distance regression): for each population and year, the greatest distance from the
   population's first observation reached so far is determined; the expansion rate is the slope of a linear
   regression of these distances on the year.

The decisions that shape the results (threshold, robust definition, years) are always yours. Where the tool makes a
suggestion (the high-resolution range of the sensitivity test), it states the rule behind it, and every result
records the settings it was made with.

## Input data

Inputs that do not meet these requirements are rejected with an explanation; nothing is guessed or repaired.

**Observations**, one of:
- **CSV**: UTF-8 ("CSV UTF-8" in Excel), comma- or semicolon-separated (recognised automatically; with semicolons,
  decimal commas are accepted in the coordinates). Required columns: `longitude`, `latitude` (WGS84 decimal degrees)
  and `year` (whole number). Optional: `location` (e.g. country; names the populations, e.g. "France 2008"),
  `source`, `source_id`. Other columns are ignored.
- **GeoPackage**: a point layer with a defined coordinate reference system and a `year` column (whole number);
  optional `location`, `source`, `source_id`. If the file has several layers, the layer must be named.
- **iNaturalist**: give the scientific name (or iNaturalist taxon ID). Observations within the extent of the cost
  surface are downloaded and assigned the country they lie in (Natural Earth). Options: research grade only
  (default), include observations with obscured coordinates (default: no), maximum positional accuracy (default:
  no limit).

**Cost surface**: a GeoTIFF in a projected coordinate reference system (metres) with square cells. Each cell's value
is the cost of moving through it; NoData cells cannot be crossed. The repository includes a demo surface for Europe
(5 km cells, [data/cost_surface_gtopo30_esri102031_5km_exp_base1_k9.tif](data/cost_surface_gtopo30_esri102031_5km_exp_base1_k9.tif)),
based on terrain only: costs from 1 to 10 increasing with elevation, derived from the
[GTOPO30](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-global-30-arc-second-elevation-gtopo30)
elevation model by USGS. For real studies, use a cost surface that reflects the species' habitat requirements (the
paper used an inverted species distribution model).

## Results

- populations (GeoPackage: paths and observations with their population), expansion rates and cumulative distances
  (CSV)
- the sensitivity test (CSV)
- the figures and tables of the paper, and plain-language checks of the chosen threshold
- one map per year end (PNG)
- `settings.txt`: all settings and numbers of the analysis in words, for the methods section

## Running it on your computer

You need Python 3.11 or newer.

```bash
git clone https://github.com/thunwal/bioinvasionanalysis.git
cd bioinvasionanalysis
python -m venv .venv
source .venv/bin/activate                      # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
```

### In the browser

```bash
python -m webapp                               # then open http://127.0.0.1:8050
```

Four steps: cost surface, observations, thresholds, export (one zip file with all results).

### Demo notebook

[notebooks/bioinvasionanalysis_demo.ipynb](notebooks/bioinvasionanalysis_demo.ipynb) downloads observations of
*Megachile sculpturalis* from iNaturalist and runs the whole analysis on the demo cost surface (`jupyter notebook`).

### Command line

An analysis is a **project folder** with a `project.toml` file that holds all settings; all results are written
into that folder.

1. `python cli.py init ~/projects/myspecies` writes a commented `project.toml`.
2. Set the observations (`[data]`) and the cost surface (`[cost]`).
3. `python cli.py sensitivity ~/projects/myspecies` imports the observations, calculates the least-cost paths and
   runs the sensitivity test. It prints the high-resolution range it chose, the rule it used, and the stable ranges.
4. Choose the threshold, e.g. at the beginning of a stable range, and run
   `python cli.py report ~/projects/myspecies --threshold <value>`. Try other values the same way; each gets its own
   folder, and the least-cost paths are reused. Put the final value into `[delineation] threshold`.
5. `python cli.py export ~/projects/myspecies` writes all results, the year maps and `settings.txt` into one zip file.

`python cli.py --help` lists all commands and options. A step is skipped if its inputs and settings have not
changed; each result folder contains a `manifest.json` stating the settings, input files and code version it was
made with.

## License

MIT, see [LICENSE](LICENSE).

---
For maintainers and developers: [docs/maintainer.md](docs/maintainer.md).
