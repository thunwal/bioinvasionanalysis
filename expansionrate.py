from datetime import datetime as dt
import os
import pandas as pd
import geopandas as gpd
import statsmodels.api as sm


def calculate_expansion_rate(in_gpkg, in_points, out_csv_rates, out_csv_rates_details):
    """
    Calculates the expansion rate for each group by regressing cumulative distance to the first point against time.
    """
    gdf_points = gpd.read_file(in_gpkg, layer=in_points)
    regression_results = []
    plot_data = []

    print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating expansion rates for presence point groups...")
    for group_id, group in gdf_points.groupby('group_id'):
        # Identify the first occurrence
        first_point = group.loc[group['observation_year'].idxmin()]
        first_point_geom = first_point.geometry

        # Calculate distances to the first point
        group['distance_to_first'] = group.geometry.distance(first_point_geom)

        # Compute the cumulative maximum distance per year
        group = group.sort_values(by='observation_year')
        group['cumulative_max_distance'] = group['distance_to_first'].cummax()

        # Regression
        x = sm.add_constant(group['observation_year'])
        y = group['cumulative_max_distance']
        model = sm.OLS(y, x).fit()

        regression_results.append({
            'group_id': group_id,
            'point_count': len(group),
            'expansion_rate': model.params[1],  # Slope of the regression line
            'r2': model.rsquared  # R2 (coefficient of determination)
        })

        # Prepare plot data
        for year, subset in group.groupby('observation_year'):
            plot_data.append({
                'group_id': group_id,
                'year': year,
                'max_distance': subset['cumulative_max_distance'].max()
            })

    pd.DataFrame(regression_results).to_csv(out_csv_rates, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Expansion rates saved to {out_csv_rates}.")

    pd.DataFrame(plot_data).to_csv(out_csv_rates_details, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Raw data saved to {out_csv_rates_details}.")
