import params
import os
import rasterio as rio
from datetime import datetime as dt
import numpy as np
from src.thinning import thin
from src.leastcostpaths import paths
from src.populations import group_paths_save, group_points_save, upper_outlier_fence
from src.expansionrate import expansion_rate_save
from src.sensitivitytest import sensitivity_analysis

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
in_lyr_points = presence_name.replace(".gpkg", "")
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
if __name__ == "__main__":
    print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from '{os.path.join(workdir_path, cost_name)}'...")
    with rio.open(os.path.join(workdir_path, cost_name)) as in_cost:
        presence_thinned, cell_size = thin(in_gpkg, in_lyr_points, in_cost, out_gpkg, out_lyr_points, out_lyr_points_thinned, year_field, start_year, end_year, location_field)
        paths(out_gpkg, out_lyr_paths, presence_thinned, in_cost, year_field, start_year, end_year)

    outlier_quantile, outlier_fence = upper_outlier_fence(out_gpkg, out_lyr_paths)

    if threshold is None:
        threshold = outlier_quantile

    group_paths_save(out_gpkg, out_lyr_paths, out_lyr_paths_grouped, threshold)
    group_points_save(out_gpkg, out_lyr_points, out_lyr_paths_grouped, out_lyr_points_grouped, cell_size)
    expansion_rate_save(out_gpkg, out_lyr_points_grouped, out_csv_rates, out_csv_cumdist, year_field, location_field)
    sensitivity_analysis(out_gpkg, out_lyr_points, out_lyr_paths, out_csv_sensitivity_test, cell_size, year_field, location_field, np.arange(0.01, 1.00, 0.01))
