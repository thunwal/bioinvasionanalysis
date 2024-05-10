from datetime import datetime as dt
import os
import rasterio as rio
import numpy as np
from thinning import thinning
from leastcostpaths import paths
from arcgis_distacc import distacc
from arcgis_optpaths import optpaths
from group import group_paths, group_points, upper_outlier_fence, sensitivity_analysis
from expansionrate import calculate_expansion_rate

# PARAMETERS ------------------------------------------------------------------
workdir_path = r"C:\Users\Christa\Documents\Git\manuscript\data"
presence_name = "msculpturalis_20240408.gpkg"  # file and layer name (without extension) of input presence point data, expected in GPKG format
year_field = "observation_year"  # field in presence data containing observation year
location_field = "country"  # field in presence data containing location (country, town or similar)
cost_name = "msculpturalis_sdm_clip_rev_scaled100.tif"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100   _scaled100   costs_with_barriers
run = "msculp20240408_sdmrev100_95q_group"  # output file names will be prefixed with {run} and existing files/layers with the same name overwritten.    sdmrev100   sdmrev  costrast1   simple100
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: handle input = output
# -----------------------------------------------------------------------------

# Define dynamic names
in_gpkg = os.path.join(workdir_path, presence_name)
in_lyr_points = presence_name.replace(".gpkg","")
out_gpkg = os.path.join(workdir_path, f"{run}.gpkg")
out_lyr_points = f"{run}_points"
out_lyr_points_thinned = f"{run}_points_thinned"
out_lyr_points_grouped = f"{run}_points_grouped"
out_lyr_paths = f"{run}_paths"
out_lyr_paths_grouped = f"{run}_paths_grouped"
out_csv_sensitivity_test = os.path.join(workdir_path, f"{run}_sensitivity_test.csv")
out_csv_rates = os.path.join(workdir_path, f"{run}_expansion_rates_results.csv")
out_csv_rates_details = os.path.join(workdir_path, f"{run}_expansion_rates_plot_data.csv")

# Execute functions
# tbd: enable skipping of the (potentially time-consuming) thinning step if GPKG is already there (read from GPKG)?
# tbd: make sure ArcGIS workflow works with same inputs (let ArcGIS read from GeoPackage?)

# =============================================================================
# Option 1: scikit-image
# =============================================================================

print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from {os.path.join(workdir_path, cost_name)}...")
in_cost = rio.open(os.path.join(workdir_path, cost_name))

presence_thinned, cell_size = thinning(in_gpkg, in_lyr_points, in_cost, out_gpkg, out_lyr_points, out_lyr_points_thinned, year_field, location_field)
paths(out_gpkg, out_lyr_paths, presence_thinned, in_cost, year_field, start_year, end_year)
outlier_quantile, outlier_fence = upper_outlier_fence(out_gpkg, out_lyr_paths)
sensitivity_analysis(out_gpkg, out_lyr_paths, out_csv_sensitivity_test, np.arange(outlier_quantile, 1.00, 0.001))
group_paths(out_gpkg, out_lyr_paths, out_lyr_paths_grouped, 0.95)
group_points(out_gpkg, out_lyr_points, out_lyr_paths_grouped, out_lyr_points_grouped, cell_size)
calculate_expansion_rate(out_gpkg, out_lyr_points_grouped, out_csv_rates, out_csv_rates_details)

# =============================================================================
# Option 2: ArcGIS Pro
# =============================================================================

# PARAMETERS ------------------------------------------------------------------
# gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
# cost = "costs_without_barriers"
# -----------------------------------------------------------------------------

# distacc(gdb, presence_name, cost, run, year_field, start_year, end_year)
# optpaths(gdb, presence_name, run, year_field, start_year, end_year)
