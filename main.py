from datetime import datetime as dt
import os
import rasterio as rio
import numpy as np
from thinning import thinning
from leastcostpaths import paths
from distacc import distacc
from optpaths import optpaths
from group import sensitivity_analysis, group_paths, upper_outlier_fence

# PARAMETERS ------------------------------------------------------------------
workdir_path = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse"
presence_name = "msculpturalis_20240408"  # file and layer name (without extension) of input presence point data, expected in GPKG format
cost_name = "msculpturalis_sdm_clip_rev_scaled100.tif"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100   _scaled100   costs_with_barriers
run = "sdmrev100"  # output names will be prefixed {presence}_{run} and existing files/layers with the same name overwritten.    sdmrev100   sdmrev  costrast1   simple100
year_field = "observation_year"  # field in presence data containing observation year
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: input = output does not work
# -----------------------------------------------------------------------------

# Define dynamic parameters
out_gpkg = os.path.join(workdir_path, f"{presence_name}_{run}.gpkg")
out_lyr_thinned = f"{presence_name}_{run}_thinned"
out_lyr_paths = f"{presence_name}_{run}_paths"
out_lyr_paths_grouped = f"{presence_name}_{run}_paths_grouped"

# Execute functions
# tbd: enable skipping of the (potentially time-consuming) thinning step if GPKG is already there (read from GPKG)?
# tbd: make sure ArcGIS workflow works with same inputs (let ArcGIS read from GeoPackage?)

#presence_thinned = thinning(workdir_path, presence_name, cost, run, year_field)

# =============================================================================
# Option 1: scikit-image
# =============================================================================

# Read cost raster
#print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from {os.path.join(workdir_path, cost_name)}...")
#cost = rio.open(os.path.join(workdir_path, cost_name))
#paths(out_gpkg, out_lyr_paths, presence_thinned, cost, year_field, start_year, end_year)
outlier_quantile, outlier_fence = upper_outlier_fence(out_gpkg, out_lyr_paths)
sensitivity_analysis(workdir_path, out_gpkg, out_lyr_paths, np.arange(outlier_quantile, 1.00, 0.001))
group_paths(out_gpkg, out_lyr_paths, out_lyr_paths_grouped, outlier_quantile)

# =============================================================================
# Option 2: ArcGIS Pro
# =============================================================================

# PARAMETERS ------------------------------------------------------------------
# gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
# cost = "costs_without_barriers"
# -----------------------------------------------------------------------------

# distacc(gdb, presence_name, cost, run, year_field, start_year, end_year)
# optpaths(gdb, presence_name, run, year_field, start_year, end_year)
