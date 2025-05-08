import params
import os
import rasterio as rio
from datetime import datetime as dt
from src.thinning import thin
from src.leastcostpaths import paths
from src.populations import group_paths_save, group_points_save, statistics
from src.expansionrate import expansion_rate_save
from src.sensitivitytest import sensitivity_analysis

# Load parameters
workdir_path = params.workdir_path
run = params.run
threshold = getattr(params, 'threshold', None)
threshold_is_absolute = getattr(params, 'threshold_is_absolute', None)
presence_name = params.presence_name
year_field = params.year_field
location_field = params.location_field
start_year = params.start_year
end_year = params.end_year
cost_name = params.cost_name
mode = params.mode
test_steps = getattr(params, 'test_steps', None)
steps_are_absolute = getattr(params, 'steps_are_absolute', None)

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


def run_analysis_pipeline():
    """Run the main analysis pipeline (thinning, paths, grouping, expansion rate)"""
    # Use global variables for threshold values
    global threshold, threshold_is_absolute

    print(f"[{dt.now().strftime('%H:%M:%S')}] Loading cost raster from '{os.path.join(workdir_path, cost_name)}'...")
    with rio.open(os.path.join(workdir_path, cost_name)) as in_cost:
        presence_thinned, cell_size = thin(in_gpkg, in_lyr_points, in_cost, out_gpkg, out_lyr_points,
                                           out_lyr_points_thinned, year_field, start_year, end_year, location_field)
        paths(out_gpkg, out_lyr_paths, presence_thinned, in_cost, year_field, start_year, end_year)

    outlier_quantile, outlier_fence, default_test_steps = statistics(out_gpkg, out_lyr_paths)

    if threshold is None:
        threshold = outlier_quantile
        threshold_is_absolute = False

    group_paths_save(out_gpkg, out_lyr_paths, out_lyr_paths_grouped, threshold, threshold_is_absolute)
    group_points_save(out_gpkg, out_lyr_points, out_lyr_paths_grouped, out_lyr_points_grouped, cell_size)
    expansion_rate_save(out_gpkg, out_lyr_points_grouped, out_csv_rates, out_csv_cumdist, year_field, location_field)

    return cell_size, default_test_steps


def run_sensitivity_test(cell_size, default_test_steps):
    """Run the sensitivity analysis"""
    # Use global variables for step values
    global test_steps, steps_are_absolute

    # Use provided test_steps if set, otherwise use default_test_steps
    if test_steps is None:
        test_steps = default_test_steps
        steps_are_absolute = True

    print(f"[{dt.now().strftime('%H:%M:%S')}] Running sensitivity analysis...")
    sensitivity_analysis(
        out_gpkg,
        out_lyr_points,
        out_lyr_paths,
        out_csv_sensitivity_test,
        cell_size,
        year_field,
        location_field,
        test_steps,
        steps_are_absolute
    )


# Call functions based on mode
if __name__ == "__main__":
    print(f"[{dt.now().strftime('%H:%M:%S')}] Running in '{mode}' mode")

    if mode in ["analysis", "all"]:
        cell_size, default_test_steps = run_analysis_pipeline()

        if mode == "all":
            run_sensitivity_test(cell_size, default_test_steps)

    elif mode == "test":
        # For test mode, ensure the required files exist
        try:
            with rio.open(os.path.join(workdir_path, cost_name)) as in_cost:
                cell_size = in_cost.res[0]  # Get cell size from raster

            # Get default test steps from existing paths
            _, _, default_test_steps = statistics(out_gpkg, out_lyr_paths)

            run_sensitivity_test(cell_size, default_test_steps)
        except Exception as e:
            print(f"[{dt.now().strftime('%H:%M:%S')}] ERROR: {e}")
            print(
                f"[{dt.now().strftime('%H:%M:%S')}] Did you forget to run in 'analysis' mode at least once to generate least-cost paths?")

    else:
        print(
            f"[{dt.now().strftime('%H:%M:%S')}] ERROR: Invalid mode '{mode}'. Valid modes are 'analysis', 'all', or 'test'")
