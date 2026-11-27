"""
Regression test against the published Megachile sculpturalis analysis (Rohrbach et al. 2025, Landscape Ecology).

The reference inputs and outputs are read from BIOINVASION_REFERENCE_DIR (default: ../manuscript/data next to this
repository). They are not part of this repository. Every intended difference to the published outputs is listed and
explained in tests/REFERENCE.md; this file checks exactly those differences and nothing else.

Run:  python -m pytest tests            (fast, ~10 s)
      python -m pytest tests -m slow    (full sensitivity sweep as in the paper, several minutes)
"""
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio as rio
import statsmodels.api as sm
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF_DIR = os.environ.get("BIOINVASION_REFERENCE_DIR", os.path.join(os.path.dirname(REPO), "manuscript", "data"))
REF_RUN = "msculp20241203_2024_4-4"
REF_GPKG = os.path.join(REF_DIR, f"{REF_RUN}.gpkg")
REF_SWEEP = os.path.join(REF_DIR, "msculp20241203_2024_sensitivity_0-01_steps_sensitivity_test.csv")
PRESENCE = os.path.join(REF_DIR, "msculpturalis_20241203.gpkg")
COST = os.path.join(REF_DIR, "sdm_esri-102031_inverted_scaled-0-1.tif")

# Settings of the published run (methods and results sections of the paper)
YEAR, LOCATION = "observation_year", "country"
START_YEAR, END_YEAR = 2008, 2024
THRESHOLD = 4.4          # absolute accumulated cost
SWEEP_STEPS = np.arange(0.00, 67.91 + 0.01, 0.01)
ROBUST_STEPS = np.arange(5, 16, 1)

pytestmark = pytest.mark.skipif(not os.path.exists(REF_GPKG), reason=f"reference data not found in {REF_DIR}")


# ---------------------------------------------------------------------------------------------------------------------
# The only part that changes when the code structure changes: run the analysis and return its results.
# ---------------------------------------------------------------------------------------------------------------------
def run_pipeline(out_dir, sweep=False):
    import sys
    sys.path.insert(0, REPO)
    from src.thinning import thin
    from src.leastcostpaths import paths
    from src.populations import group_paths_save, group_points_save
    from src.expansionrate import expansion_rate_save
    from src.sensitivitytest import sensitivity_analysis

    gpkg = os.path.join(out_dir, "run.gpkg")
    with rio.open(COST) as cost:
        thinned, cell = thin(PRESENCE, "msculpturalis_20241203", cost, gpkg, "points", "points_thinned",
                             YEAR, START_YEAR, END_YEAR, LOCATION)
        paths(gpkg, "paths", thinned, cost, YEAR, START_YEAR, END_YEAR)
    group_paths_save(gpkg, "paths", "paths_grouped", THRESHOLD, threshold_is_absolute=True)
    group_points_save(gpkg, "points", "paths_grouped", "points_grouped", cell)
    rates_csv, cumdist_csv = os.path.join(out_dir, "rates.csv"), os.path.join(out_dir, "cumdist.csv")
    expansion_rate_save(gpkg, "points_grouped", rates_csv, cumdist_csv, YEAR, LOCATION)
    result = {lyr: gpd.read_file(gpkg, layer=lyr)
              for lyr in ["points", "points_thinned", "paths", "paths_grouped", "points_grouped"]}
    result["expansion_rates"] = pd.read_csv(rates_csv)
    result["cumulative_distances"] = pd.read_csv(cumdist_csv)
    if sweep:
        sweep_csv = os.path.join(out_dir, "sweep.csv")
        sensitivity_analysis(gpkg, "points", "paths", sweep_csv, cell, YEAR, LOCATION, SWEEP_STEPS, True, ROBUST_STEPS)
        result["sweep"] = pd.read_csv(sweep_csv)
    return result
# ---------------------------------------------------------------------------------------------------------------------


def ref(layer):
    return gpd.read_file(REF_GPKG, layer=f"{REF_RUN}_{layer}")


def ref_csv(name):
    return pd.read_csv(os.path.join(REF_DIR, f"{REF_RUN}_{name}.csv"))


def keys(gdf):
    """Identifies points by rounded coordinates (mm) and year."""
    return list(zip(np.round(gdf.geometry.x, 3), np.round(gdf.geometry.y, 3), gdf[YEAR]))


def on_nodata(gdf):
    with rio.open(COST) as cost:
        values = np.array([v[0] for v in cost.sample(zip(gdf.geometry.x, gdf.geometry.y))], dtype=float)
        return np.isnan(values) | (values == cost.nodata)


@pytest.fixture(scope="module")
def new(tmp_path_factory):
    return run_pipeline(str(tmp_path_factory.mktemp("run")))


# REFERENCE.md, difference 1: observations on NoData cells are removed (commit 3c3ef92)
@pytest.mark.parametrize("layer, n_removed", [("points", 6), ("points_thinned", 5)])
def test_points_only_nodata_removed(new, layer, n_removed):
    old = ref(layer)
    new_keys = set(keys(new[layer]))
    removed = old[[k not in new_keys for k in keys(old)]]
    assert len(new[layer]) == len(old) - n_removed
    assert len(removed) == n_removed
    assert on_nodata(removed).all()
    assert not on_nodata(new[layer]).any()


@pytest.mark.parametrize("layer", ["paths", "paths_grouped"])
def test_paths_identical(new, layer):
    old, cur = ref(layer), new[layer]
    assert len(cur) == len(old)
    assert cur.geometry.geom_equals_exact(old.geometry, tolerance=1e-6).all()
    np.testing.assert_allclose(cur["accumulated_cost"], old["accumulated_cost"], rtol=1e-9)
    if "group_id" in old:
        assert (cur["group_id"].astype(str).values == old["group_id"].astype(str).values).all()


def test_points_grouped_identical(new):
    old, cur = ref("points_grouped"), new["points_grouped"]
    old = old[[k in set(keys(cur)) for k in keys(old)]].reset_index(drop=True)
    assert len(old) == len(cur)
    assert (old["group_id"].fillna("").astype(str).values == cur["group_id"].fillna("").astype(str).values).all()


def test_cumulative_distances_identical(new):
    pd.testing.assert_frame_equal(new["cumulative_distances"], ref_csv("cumulative_distances"), check_dtype=False,
                                  rtol=1e-9)


def test_expansion_rates(new):
    """
    REFERENCE.md, difference 2: expansion rates follow the paper's methods text, i.e. one value per year (the yearly
    cumulative maximum distance, = cumulative_distances.csv) is regressed against year. The expected values are
    computed here from the published cumulative distances, which do not depend on the row order.
    REFERENCE.md, difference 1: France 2008 has one observation less (on a NoData cell).
    """
    old, cur = ref_csv("expansion_rates"), new["expansion_rates"]
    cols = ["group_id", "first_observed_in", "min_year", "max_year", "median_points_per_year"]
    pd.testing.assert_frame_equal(cur[cols], old[cols], check_dtype=False)
    old_points = ref("points_grouped")
    kept = old_points[[k in set(keys(new["points"])) for k in keys(old_points)]].dropna(subset=["group_id"])
    expected_count = kept.groupby(kept["group_id"].astype(int)).size().reindex(old["group_id"]).values
    assert (cur["point_count"].values == expected_count).all()
    assert (old["point_count"].values - expected_count).sum() == 1  # the France 2008 observation on a NoData cell

    expected = {}
    for gid, d in ref_csv("cumulative_distances").groupby("group_id"):
        model = sm.OLS(d["max_distance"], sm.add_constant(d["year"])).fit()
        expected[gid] = (model.params.iloc[1], model.rsquared)
    expected = np.array([expected[gid] for gid in cur["group_id"]])
    np.testing.assert_allclose(cur["expansion_rate"], expected[:, 0], rtol=1e-9)
    np.testing.assert_allclose(cur["r2"], expected[:, 1], rtol=1e-9)


@pytest.mark.slow
def test_sweep(tmp_path_factory):
    """
    The number of populations per threshold does not depend on the expansion rate method or the robust definition,
    so it must equal the published sweep. The robust columns are compared in REFERENCE.md, difference 3.
    """
    cur = run_pipeline(str(tmp_path_factory.mktemp("sweep")), sweep=True)["sweep"]
    old = pd.read_csv(REF_SWEEP)
    assert len(cur) == len(old)
    np.testing.assert_allclose(cur["threshold"], old["threshold"], atol=1e-9)
    assert (cur["num_groups"].values == old["num_groups"].values).all()
