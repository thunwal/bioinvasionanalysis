# Regression reference

The regression test (`tests/test_regression.py`) compares the code with the published *Megachile sculpturalis*
analysis (Rohrbach et al. 2025, *Landscape Ecology*, https://doi.org/10.1007/s10980-025-02188-9).

## Reference data
Read from `BIOINVASION_REFERENCE_DIR`, by default `../manuscript/data`. They are not part of this repository.

| File | Content |
|---|---|
| `msculpturalis_20241203.gpkg` | input observations (2247) |
| `sdm_esri-102031_inverted_scaled-0-1.tif` | input cost surface (10 km) |
| `msculp20241203_2024_4-4.gpkg` | published run: points, thinned points, paths (886), grouped paths and points |
| `msculp20241203_2024_4-4_expansion_rates.csv`, `..._cumulative_distances.csv` | published results |
| `msculp20241203_2024_sensitivity_0-01_steps_sensitivity_test.csv` | published sensitivity sweep |

Settings of the published run, reconstructed from the paper and confirmed by the test:
- years 2008–2024
- year field `observation_year`, location field `country`
- absolute threshold 4.4
- sweep 0–67.91 in steps of 0.01, robust definitions 5–15

## How to use
- Run `python -m pytest` before every merge, and `python -m pytest -m slow` before merging anything that touches the
  sweep.
- A change that is meant to change results gets **its own commit**, which updates the test and adds a section
  below explaining what changed, why, and how large the effect is.

## Intended differences to the published outputs

### 1. Observations on NoData cells are removed (commit 3c3ef92, 2026-11-23)
Least-cost paths can never reach a NoData cell (e.g. sea), so such observations are now removed during import.
- 6 observations are removed: Ukraine 2022 and 2023, Italy 2019 and 2023, Spain 2021 and 2024.
- 5 thinned points are removed.
- Paths and groups are unchanged.
- One removed observation (Spain 2024) had been assigned to the France 2008 population, so its point count drops
  from 1000 to 999. All other observations keep their group.

### 2. Expansion rates follow the methods text (one value per year)
**Paper:** "Using the distances, calculate the cumulative maximum *for each year* … the limited number of data points
(*one per year*), inherent to the distance regression method".

**Old code:**
- It sorted all observations of a population by year and took the running maximum *per observation*.
- It then regressed every observation against year.
- Within a year, the running maximum an observation got depended on the arbitrary row order (`sort_values` is not
  stable). So results changed with the order of the input rows and with the pandas version:
  - Shuffling the rows changed rates by up to 7 km/yr and R² by up to 0.35.
  - The published `points_grouped` layer, run through the same code today, gives rates up to 3.3 km/yr different
    from the published table.

**New code:** regresses the yearly cumulative maximum distance (exactly the values in `cumulative_distances.csv`)
against year. This is independent of the row order. The published cumulative distances are reproduced exactly.

Effect on the robust populations of the published run (threshold 4.4, median > 10):

| Population | published (per observation) | new (one value per year) |
|---|---|---|
| Italy 2009 | 58.6 km/yr, R² 0.78 | 67.2 km/yr, R² 0.95 |
| France 2008 | 52.4 km/yr, R² 0.85 | 65.1 km/yr, R² 0.93 |
| Austria 2017 | 13.3 km/yr, R² 0.83 | 11.7 km/yr, R² 0.92 |
| Serbia 2017 | 38.3 km/yr, R² 0.68 | 35.4 km/yr, R² 0.90 |

The phase regressions of the paper (breakpoints, done in R on `cumulative_distances.csv`) already used one value per
year and are not affected.

Decided by the author on 2026-11-27: follow the paper text.

### 3. Robust populations: median *above* the definition (`>`), also in the sweep
**Paper:** "Populations with a median above 10 were classified as robust". The R code of the paper uses `> 10`.

**Old code:** the delineation, report and animation used `>`, but the sensitivity sweep used `>=`.

**New code:** one helper, `is_robust()`, is used everywhere and applies `>`.

The published delineation results are unaffected, because they were classified with `> 10` in R. In the sweep, only
the robust columns change (`num_groups_robust`, `min_rate`, `max_rate`, `avg_rate`), and only where a population's
median equals an integer robust definition exactly. The published sweep (Fig. 3a) was computed with `>=` and the old
expansion rate method (difference 2). The number of populations per threshold (`num_groups`) is unchanged; the slow
test checks it against the published sweep.

Measured on the published sweep (74712 rows = 6792 thresholds × 11 robust definitions): with `>` instead of `>=`,
the number of robust populations differs in 1171 rows (1.6 %), for robust definitions 5–14.
