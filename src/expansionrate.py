from datetime import datetime as dt
import pandas as pd
import geopandas as gpd
import statsmodels.api as sm


def expansion_rate(in_gpkg, in_points, out_csv_rates, out_csv_rates_details, year_field):
    """
    Calculates the expansion rate for each population by regressing cumulative distance to the first point against time.
    """
    gdf_points = gpd.read_file(in_gpkg, layer=in_points)
    exp_rates = []
    cum_distances = []

    print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating expansion rates for groups (populations)...")
    for group_id, group in gdf_points.groupby('group_id'):
        # Identify the first occurrence
        first_point = group.loc[group[year_field].idxmin()]
        first_point_geom = first_point.geometry

        # Calculate distances to the first point
        group['distance_to_first'] = group.geometry.distance(first_point_geom)

        # Compute the cumulative maximum distance per year
        group = group.sort_values(by=year_field)
        group['cumulative_max_distance'] = group['distance_to_first'].cummax()

        # Calculate stats
        annual_counts = group.groupby(year_field).size()
        median_observations_per_year = annual_counts.median()
        min_year = group[year_field].min()
        max_year = group[year_field].max()

        # Append result to list
        for year, subset in group.groupby(year_field):
            cum_distances.append({
                'group_id': group_id,
                'year': int(year),
                'max_distance': subset['cumulative_max_distance'].max()
            })

        # Regression
        x = sm.add_constant(group[year_field])
        y = group['cumulative_max_distance']
        model = sm.OLS(y, x).fit()

        # Append result to list
        exp_rates.append({
            'group_id': group_id,
            'min_year': int(min_year),
            'max_year': int(max_year),
            'point_count': len(group),
            'median_points_per_year': median_observations_per_year,
            'expansion_rate': model.params.iloc[1],  # Slope of the regression line
            'r2': model.rsquared  # Model strength (coefficient of determination)
        })

    # Save cumulative max. distance results
    pd.DataFrame(cum_distances).to_csv(out_csv_rates_details, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Raw data saved to '{out_csv_rates_details}'.")

    # Save regression results
    pd.DataFrame(exp_rates).to_csv(out_csv_rates, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Expansion rates saved to '{out_csv_rates}'.")

    # Return dataframes (currently only needed for the usage in Jupyter notebook)
    return pd.DataFrame(cum_distances), pd.DataFrame(exp_rates)
