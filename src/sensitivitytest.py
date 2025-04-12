from datetime import datetime as dt
import numpy as np
import pandas as pd
import geopandas as gpd
from src.populations import group_paths, group_points
from src.expansionrate import expansion_rate


def sensitivity_analysis(in_gpkg, in_points, in_paths, out_csv_outlier_test, cell_size, year_field, location_field, quantile_range):
    """
    Runs a sensitivity analysis over a range of thresholds (quantiles) to determine the impact on the number of resulting populations.
    """
    gdf_points = gpd.read_file(in_gpkg, layer=in_points)
    gdf_paths = gpd.read_file(in_gpkg, layer=in_paths)

    print(f"[{dt.now().strftime('%H:%M:%S')}] ########### SENSITIVITY TEST ###########")
    print(f"[{dt.now().strftime('%H:%M:%S')}] Testing accumulated cost thresholds from Q{round(quantile_range[0],3)} to Q{round(quantile_range[-1],3)}...")

    results = []

    for quantile in quantile_range:
        # Copy the GeoDataFrame to avoid modifying the original
        gdf_points_copy = gdf_points.copy()
        gdf_paths_copy = gdf_paths.copy()

        # Apply quantile threshold to filter paths
        threshold = np.quantile(gdf_paths_copy['accumulated_cost'], quantile)
        gdf_paths_copy = gdf_paths_copy[gdf_paths_copy['accumulated_cost'] < threshold]

        # Group paths and assign population IDs based on connectivity
        grouped_paths = group_paths(gdf_paths_copy)

        # Group points and assign population IDs based on nearness to grouped paths
        grouped_points = group_points(gdf_points_copy, grouped_paths, cell_size)

        # Calculate expansion rates and stats for populations
        _, exp_rates = expansion_rate(grouped_points, year_field, location_field)

        # Count populations overall and for robust populations
        num_groups = exp_rates['group_id'].nunique()
        robust_populations = exp_rates[exp_rates['median_points_per_year'] > 10]
        num_groups_robust = robust_populations['group_id'].nunique()

        # Calculate min, max and avg expansion rate across robust populations
        min_rate = robust_populations['expansion_rate'].min()
        max_rate = robust_populations['expansion_rate'].max()
        avg_rate = robust_populations['expansion_rate'].mean()

        # Record the results
        results.append({'quantile': quantile,
                        'threshold': threshold,
                        'num_groups': num_groups,
                        'num_groups_robust': num_groups_robust,
                        'min_rate': min_rate,
                        'max_rate': max_rate,
                        'avg_rate': avg_rate
                        })

    pd.DataFrame(results).to_csv(out_csv_outlier_test, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Test results saved to '{out_csv_outlier_test}'.")
