from datetime import datetime as dt
import pandas as pd
import geopandas as gpd
import statsmodels.api as sm
from shapely.geometry import MultiPoint


def expansion_rate(in_points, year_field, location_field):
    """
    Calculates the expansion rate for each population by regressing cumulative distance to the first point against time.
    """
    gdf_points = in_points.dropna(subset=[year_field, 'geometry', 'group_id']).astype({year_field: 'int32', 'group_id': 'string'})
    exp_rates = []
    cum_distances = []

    print(f"[{dt.now().strftime('%H:%M:%S')}] Calculating expansion rates for groups (populations)...")
    for group_id, population in gdf_points.groupby('group_id'):
        # Identify the point(s) from the first year
        first_year = population[year_field].min()
        first_year_points = population[population[year_field] == first_year]
        first_year_geoms = first_year_points.geometry

        # If multiple points, aggregate to a single reference point
        if len(first_year_geoms) > 1:
            reference_point = MultiPoint(first_year_geoms.geometry.tolist()).centroid
        else:
            reference_point = first_year_geoms.iloc[0]

        # Calculate distances to the reference point
        population['distance_to_first'] = population.geometry.distance(reference_point)

        # Compute the cumulative maximum distance per year
        population = population.sort_values(by=year_field)
        population['cumulative_max_distance'] = population['distance_to_first'].cummax()

        # Append result to list
        for year, subset in population.groupby(year_field):
            cum_distances.append({
                'group_id': group_id,
                'year': year,
                'max_distance': subset['cumulative_max_distance'].max()
            })

        # Calculate stats
        # Fill years without observations with 0 values for the median calculation
        min_year = population[year_field].min()
        max_year = population[year_field].max()
        all_years = pd.Series(range(min_year, max_year + 1), name=year_field)
        annual_counts = population.groupby(year_field).size().reindex(all_years, fill_value=0)
        median_annual_count = annual_counts.median()
        first_observed_in = " / ".join(first_year_points[location_field].unique())

        # Regression
        x = sm.add_constant(population[year_field])
        y = population['cumulative_max_distance']
        model = sm.OLS(y, x).fit()

        # Append result to list
        exp_rates.append({
            'group_id': group_id,
            'first_observed_in': first_observed_in,
            'min_year': min_year,
            'max_year': max_year,
            'point_count': len(population),
            'median_points_per_year': median_annual_count,
            'expansion_rate': model.params.iloc[1],  # Slope of the regression line
            'r2': model.rsquared  # Model strength (coefficient of determination)
        })

    return pd.DataFrame(cum_distances).astype({'group_id': 'string'}), pd.DataFrame(exp_rates).astype({'group_id': 'string'})


def expansion_rate_save(in_gpkg, in_points, out_csv_rates, out_csv_rates_details, year_field, location_field):
    """
    Reads from and writes to GeoPackage, wrapping the expansion_rate() function.
    """
    gdf_points = gpd.read_file(in_gpkg, layer=in_points)

    cum_distances, exp_rates = expansion_rate(gdf_points, year_field, location_field)

    # Save cumulative max. distance results
    cum_distances.to_csv(out_csv_rates_details, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Raw data saved to '{out_csv_rates_details}'.")

    # Save regression results
    exp_rates.to_csv(out_csv_rates, index=False)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Expansion rates saved to '{out_csv_rates}'.")

    # Return dataframes (currently only needed for the usage in Jupyter notebook)
    return cum_distances, exp_rates
