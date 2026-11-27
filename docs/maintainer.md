# Maintainer notes

Everything about keeping the code correct and running. The [README](../README.md) is for users.

| Document | Content |
|---|---|
| [architecture.md](architecture.md) | how the code is organised, where to change what, debugging |
| [deployment.md](deployment.md) | Docker image, Hugging Face Space |
| [../tests/REFERENCE.md](../tests/REFERENCE.md) | the regression reference and every intended difference to the published results |
| [../CHANGES.md](../CHANGES.md) | what changed, and whether results changed |

## Before every merge into main

```bash
python -m pytest              # about 30 s
python -m pytest -m slow      # additionally the full sensitivity test of the paper (several minutes);
                              # needed if anything in bioinvasion/core or the sensitivity test changed
```

- `tests/test_regression.py` runs the current code on the input data of the paper and compares every result with
  the results published with the paper. The reference data are not in this repository; they are read from
  `BIOINVASION_REFERENCE_DIR` (default `../manuscript/data`). Without them, the regression tests are skipped.
- `tests/test_cli.py` runs invented observations (`tests/synthetic.py`) through `cli.py` from import to export.
- `tests/test_import.py` checks the input rules, `tests/test_webapp_jobs.py` the session folders of the web app.
- If a result changes on purpose: change the test in the same commit and add a section to `tests/REFERENCE.md`.

## Web app in a browser (manual)

`tests/e2e_webapp.py` clicks through all four pages in a headless browser and downloads the export. It needs
Playwright, which is not in the requirements:

```bash
pip install playwright && python -m playwright install chromium     # once, in the project environment
DASH_DEBUG=0 python -m webapp                                       # terminal 1
python tests/e2e_webapp.py . /tmp/e2e                               # terminal 2; screenshots and zip in /tmp/e2e
```

## Things to know

- The public web app runs at https://huggingface.co/spaces/thunwal/bioinvasionanalysis. After changes to
  `bioinvasion/` or `webapp/`, update it as described in [deployment.md](deployment.md#updating-the-space).
- `data/` is ignored by git except the demo cost surface; keep private data and run outputs there or anywhere else.
- Personal scripts (animation, data preparation) live in a separate repository, `bioinvasion-personal`, which uses
  this package.
- Open scientific question: observations are assigned to the nearest path endpoint within half a cell diagonal,
  which can be a neighbouring cell, whereas the paper says "same cell". Not decided yet.
