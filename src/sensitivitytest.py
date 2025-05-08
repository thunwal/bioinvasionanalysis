from datetime import datetime as dt
import numpy as np
import pandas as pd
import geopandas as gpd
from src.populations import group_paths, group_points
from src.expansionrate import expansion_rate


def sensitivity_analysis(in_gpkg, in_points, in_paths, out_csv_outlier_test, cell_size, year_field, location_field, acc_cost_test_steps, acc_cost_steps_are_absolute, robust_test_steps):
    """
    Runs a sensitivity analysis over a range of thresholds (quantiles) to determine the impact on the number of resulting populations.
    """
    gdf_points = gpd.read_file(in_gpkg, layer=in_points)
    gdf_paths = gpd.read_file(in_gpkg, layer=in_paths)

    if acc_cost_steps_are_absolute:
        print(f"[{dt.now().strftime('%H:%M:%S')}] Testing accumulated cost thresholds (absolute) from {round(acc_cost_test_steps[0],3)} to {round(acc_cost_test_steps[-1],3)} and robust population definitions from {robust_test_steps[0]} to {robust_test_steps[-1]} median observations per year...")
    else:
        print(f"[{dt.now().strftime('%H:%M:%S')}] Testing accumulated cost thresholds (quantiles) from Q{round(acc_cost_test_steps[0],3)} to Q{round(acc_cost_test_steps[-1],3)} and robust population definitions from {robust_test_steps[0]} to {robust_test_steps[-1]} median observations per year...")

    results = []

    for step in acc_cost_test_steps:
        # Copy the GeoDataFrame to avoid modifying the original
        gdf_points_copy = gdf_points.copy()
        gdf_paths_copy = gdf_paths.copy()

        # Calculate threshold to filter paths
        if acc_cost_steps_are_absolute:
            # Treat input value as an absolute value
            threshold = step
            # Calculate what quantile this represents (percentage of values below the threshold)
            values_below_threshold = pd.Series(gdf_paths_copy['accumulated_cost'] < threshold).sum()
            total_values = len(gdf_paths_copy)
            quantile = values_below_threshold / total_values
        else:
            # Treat input value as a quantile
            quantile = step
            threshold = np.quantile(gdf_paths_copy['accumulated_cost'], quantile)

        # Apply quantile threshold to filter paths
        gdf_paths_copy = gdf_paths_copy[gdf_paths_copy['accumulated_cost'] < threshold]

        if len(gdf_paths_copy) == 0:
            # No paths meets threshold criterion, set default values
            for robust_step in robust_test_steps:
                results.append({
                    'quantile': quantile,
                    'threshold': threshold,
                    'definition_robust': robust_step,
                    'num_groups': 0,
                    'num_groups_robust': 0,
                    'min_rate': float('nan'),
                    'max_rate': float('nan'),
                    'avg_rate': float('nan')
                })
        else:
            # Group paths and assign population IDs based on connectivity
            grouped_paths = group_paths(gdf_paths_copy)

            # Group points and assign population IDs based on nearness to grouped paths
            grouped_points = group_points(gdf_points_copy, grouped_paths, cell_size)

            # Calculate expansion rates and stats for populations
            _, exp_rates = expansion_rate(grouped_points, year_field, location_field)

            # Count populations overall and for robust populations
            num_groups = exp_rates['group_id'].nunique()

            # Inner loop to test different definitions of robust populations
            for robust_step in robust_test_steps:
                robust_populations = exp_rates[exp_rates['median_points_per_year'] >= robust_step]
                num_groups_robust = robust_populations['group_id'].nunique()

                # Calculate min, max and avg expansion rate across robust populations
                min_rate = robust_populations['expansion_rate'].min()
                max_rate = robust_populations['expansion_rate'].max()
                avg_rate = robust_populations['expansion_rate'].mean()

                # Record the results
                results.append({'quantile': quantile,
                                'threshold': threshold,
                                'definition_robust': robust_step,
                                'num_groups': num_groups,
                                'num_groups_robust': num_groups_robust,
                                'min_rate': min_rate,
                                'max_rate': max_rate,
                                'avg_rate': avg_rate
                                })

    pd.DataFrame(results).to_csv(out_csv_outlier_test, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Test results saved to '{out_csv_outlier_test}'.")
