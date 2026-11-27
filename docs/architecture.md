# How the code is organised

## The idea in one picture

```
 cli.py  ─┐                                      (front ends: read user input, show results)
 webapp/ ─┼──>  bioinvasion/pipeline.py          (files, folders, manifests: the only module that reads/writes)
 notebook ┘          │
                     ├──> bioinvasion/sources/   (stage 1: CSV, GPKG, iNaturalist → standard presence schema)
                     ├──> bioinvasion/core/      (the science: GeoDataFrames in, GeoDataFrames out, no files)
                     └──> bioinvasion/report/    (figures, tables, suggestions and checks)
```

- **core/** contains the methods of the paper. Each function takes data (GeoDataFrames, an open raster) and returns
  data. It never decides file names and never writes files, so it can be called from anywhere: the CLI, the web app,
  a notebook, a test.
- **pipeline.py** knows the project folder layout. For each stage it reads the inputs, calls the core functions,
  writes the outputs and a `manifest.json`, and skips the stage if the manifest shows nothing has changed.
- **cli.py** and **webapp/** only translate between people and `pipeline`. If something is computed differently in
  the CLI and the web app, that is a bug.

## Where do I change what?

| I want to … | File |
|---|---|
| change how paths, populations or expansion rates are calculated | `bioinvasion/core/*.py` (then run the tests) |
| change the definition of "robust" | `bioinvasion/core/robust.py` (one line, used everywhere) |
| accept another input format or change the input rules | `bioinvasion/sources/files.py` |
| add a setting | `bioinvasion/config.py` (dataclass + template), then use it in `pipeline.py` |
| change output file names or folders | `bioinvasion/pipeline.py` |
| change a figure or table | `bioinvasion/report/figures.py` |
| change the suggested sweep range or the checks | `bioinvasion/report/insights.py` |
| add a command line option | `cli.py` |

## The standard presence schema

Every import ends in the same columns: `year`, `location`, `source`, `source_id`, point geometry in WGS84. The core
functions rely on these names, so there are no "year_field" settings anywhere.

## Debugging

**A core function, in a notebook or console**: load the inputs of a finished stage and call the function directly.

```python
from bioinvasion.pipeline import load_paths
from bioinvasion.core.populations import delineate
from bioinvasion.core.expansionrate import expansion_rate

run = load_paths("examples/isodontia/paths__gtopo30exp5km__1993-2024")
paths_grouped, points_grouped, share = delineate(run["paths"], run["points"], 0.19, run["cell_size"])
cumulative_distances, rates = expansion_rate(points_grouped)
```

**With breakpoints in VS Code**: add this to `.vscode/launch.json`, set a breakpoint in any file and press F5.

```json
{
  "version": "0.2.0",
  "configurations": [
    {"name": "cli: report demo", "type": "debugpy", "request": "launch", "program": "${workspaceFolder}/cli.py",
     "args": ["report", "examples/isodontia", "--threshold", "0.19"], "console": "integratedTerminal"},
    {"name": "tests", "type": "debugpy", "request": "launch", "module": "pytest", "args": ["-x"],
     "console": "integratedTerminal"}
  ]
}
```

**A stage that is skipped although it should run**: delete its `manifest.json` (or use `--force` for import and
paths). The manifest also shows which settings and inputs the existing results were made with.

## Tests

`tests/test_regression.py` runs the published analysis through `pipeline` and compares every output with the paper.
`tests/REFERENCE.md` lists each intended difference with its reason. Before merging any change: `python -m pytest`
(and `python -m pytest -m slow` if the sweep is affected). If a result changes on purpose, change the test in the same
commit and add a section to `REFERENCE.md`.
