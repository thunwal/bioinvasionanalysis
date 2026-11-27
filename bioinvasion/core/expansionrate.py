import pandas as pd
import statsmodels.api as sm
from shapely.geometry import MultiPoint


def expansion_rate(points_grouped):
    """
    Expansion rate per population by distance regression (Rohrbach et al. 2025, methods):
    1. Reference point: the first observation of the population (centroid, if there are several in the first year).
    2. Cumulative maximum distance: for each year, the farthest distance to the reference point reached up to and
       including that year. One value per year with observations.
    3. Linear regression (OLS) of these yearly values against year. The slope is the expansion rate in m/year.

    Returns (cumulative_distances, expansion_rates) as DataFrames. Observations without group_id are ignored.
    """
    points = points_grouped.dropna(subset=["year", "geometry", "group_id"]).astype({"year": "int32",
                                                                                    "group_id": "string"})
    rates, cum_distances = [], []

    for group_id, population in points.groupby("group_id"):
        first_year = population["year"].min()
        first_year_points = population[population["year"] == first_year]
        if len(first_year_points) > 1:
            reference_point = MultiPoint(first_year_points.geometry.tolist()).centroid
        else:
            reference_point = first_year_points.geometry.iloc[0]

        distance = population.geometry.distance(reference_point)
        yearly = distance.groupby(population["year"]).max().sort_index().cummax()
        cum_distances += [{"group_id": group_id, "year": year, "max_distance": d} for year, d in yearly.items()]

        # Median observations per year, counting years without observations as 0
        max_year = population["year"].max()
        annual_counts = population.groupby("year").size().reindex(range(first_year, max_year + 1), fill_value=0)

        model = sm.OLS(yearly.to_numpy(), sm.add_constant(pd.Series(yearly.index, name="year", dtype="float64"))).fit()
        rates.append({
            "group_id": group_id,
            "first_observed_in": " / ".join(first_year_points["location"].fillna("").astype(str).unique()),
            "min_year": first_year,
            "max_year": max_year,
            "point_count": len(population),
            "median_points_per_year": annual_counts.median(),
            "expansion_rate": model.params.iloc[1],  # slope of the regression line, m/year
            # R² is undefined if the distance never changes (e.g. two years at the same distance)
            "r2": model.rsquared if yearly.nunique() > 1 else float("nan"),
        })

    return (pd.DataFrame(cum_distances, columns=["group_id", "year", "max_distance"]).astype({"group_id": "string"}),
            pd.DataFrame(rates, columns=["group_id", "first_observed_in", "min_year", "max_year", "point_count",
                                         "median_points_per_year", "expansion_rate", "r2"]).astype({"group_id": "string"}))
