import params
import os
import rasterio as rio
import numpy as np
from datetime import datetime as dt
from thinning import thin
from leastcostpaths import paths
from populations import group_paths, group_points, upper_outlier_fence, sensitivity_analysis
from expansionrate import expansion_rate
#from arcgis_distacc import distacc
#from arcgis_optpaths import optpaths

# Load parameters
workdir_path = params.workdir_path
run = params.run
threshold = getattr(params, 'threshold', None)
presence_name = params.presence_name
year_field = params.year_field
location_field = params.location_field
start_year = params.start_year
end_year = params.end_year
cost_name = params.cost_name

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
out_csv_rates = os.path.join(workdir_path, f"{run}_expansion_rates.csv")
out_csv_cumdist = os.path.join(workdir_path, f"{run}_cumulative_distances.csv")

# Call functions
print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from '{os.path.join(workdir_path, cost_name)}'...")
in_cost = rio.open(os.path.join(workdir_path, cost_name))

presence_thinned, cell_size = thin(in_gpkg, in_lyr_points, in_cost, out_gpkg, out_lyr_points, out_lyr_points_thinned, year_field, start_year, end_year, location_field)
paths(out_gpkg, out_lyr_paths, presence_thinned, in_cost, year_field, start_year, end_year)
outlier_quantile, outlier_fence = upper_outlier_fence(out_gpkg, out_lyr_paths)
sensitivity_analysis(out_gpkg, out_lyr_paths, out_csv_sensitivity_test, np.arange(outlier_quantile, 1.00, 0.001))

if threshold is None:
    threshold = outlier_quantile

group_paths(out_gpkg, out_lyr_paths, out_lyr_paths_grouped, threshold)
group_points(out_gpkg, out_lyr_points, out_lyr_paths_grouped, out_lyr_points_grouped, cell_size)
expansion_rate(out_gpkg, out_lyr_points_grouped, out_csv_rates, out_csv_cumdist, year_field)
