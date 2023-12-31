from datetime import datetime as dt
import os
import rasterio as rio
from thinning import thinning
from leastcostpaths import paths

# PARAMETERS ------------------------------------------------------------------
workdir_path = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse"
presence_name = "msculpturalis_20230925"  # file and layer name (without extension) of input presence point data, expected in GPKG format
cost_name = "msculpturalis_sdm_clip_rev_scaled100.tif"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100   _scaled100   costs_with_barriers
run = "sdmrev100"  # output names will be prefixed {presence}_{run} and existing files/layers with the same name overwritten.    sdmrev100   sdmrev  costrast1   simple100
year_field = "observation_year"  # field in presence data containing observation year
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: input = output does not work
# -----------------------------------------------------------------------------

# Read cost raster
print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from {os.path.join(workdir_path, cost_name)}...")
cost = rio.open(os.path.join(workdir_path, cost_name))
out_gpkg = os.path.join(workdir_path, f"{presence_name}_{run}.gpkg")
out_lyr_thinned = f"{presence_name}_{run}_thinned"
out_lyr_paths = f"{presence_name}_{run}_paths"

# Execute functions
# thinning() returns thinned presence data in GeoDataFrame, but also saves GPKG
# -> tbd: enable skipping of the (potentially time-consuming) thinning step if GPKG is already there
presence_thinned = thinning(workdir_path, presence_name, cost, run, year_field)
paths(out_gpkg, out_lyr_paths, presence_thinned, cost, year_field, start_year, end_year)
#distacc(presence_thinned, cost, run, year_field, start_year, end_year)
#optpaths(presence_thinned, run, year_field, start_year, end_year)
