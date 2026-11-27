"""
Prepares presence data for the least-cost analysis: keeps only observations the analysis can use, and reduces them to
the resolution of the cost surface.

Input points use the standard presence schema (columns 'year', 'location', geometry); see bioinvasion/sources.
"""
import numpy as np
import pandas as pd
from rasterio.transform import rowcol
from shapely.geometry import box


def filter_points(points, cost, start_year, end_year):
    """
    Projects the observations to the CRS of the cost surface and removes those the analysis cannot use.
    'cost' is an open rasterio dataset. Returns the remaining points and a list of (reason, number removed), which is
    written to the run's manifest so that every removed observation is accounted for.
    """
    removed = []

    def keep(mask, reason):
        nonlocal points
        removed.append((reason, int((~mask).sum())))
        points = points[mask]

    keep(points["year"].notna().to_numpy() & points.geometry.notna().to_numpy(), "no year or no geometry")
    points = points.astype({"year": "int32"})
    keep(((points["year"] >= start_year) & (points["year"] <= end_year)).to_numpy(),
         f"outside the years {start_year}-{end_year}")
    points = points.to_crs(cost.crs)
    keep(points.geometry.within(box(*cost.bounds)).to_numpy(), "outside the cost surface")
    # Least-cost paths can never reach NoData cells (e.g. sea)
    values = np.array([v[0] for v in cost.sample(zip(points.geometry.x, points.geometry.y))], dtype=float)
    on_data = ~np.isnan(values)
    if cost.nodata is not None:
        on_data &= values != cost.nodata
    keep(on_data, "on a NoData cell of the cost surface")
    return points, removed


def cell_of(points, cost):
    """Row and column of the cost surface cell that contains each point."""
    rows, cols = rowcol(cost.transform, points.geometry.x.to_numpy(), points.geometry.y.to_numpy())
    return np.asarray(rows), np.asarray(cols)


def thin(points, cost):
    """
    Keeps the earliest observation per cost surface cell. If several observations in a cell share the earliest year,
    the first one in the input order is kept. The result is ordered by cell: column by column from west to east, and
    from south to north within a column (the order the code has always used; it determines the order of the paths).
    """
    cell_size, cell_size_y = cost.res
    if cell_size != cell_size_y:
        raise ValueError(f"The cost surface must have square cells, but has {cell_size} x {cell_size_y}.")
    rows, cols = cell_of(points, cost)
    order = pd.DataFrame({"col": cols, "row_from_south": cost.height - 1 - rows, "year": points["year"].to_numpy(),
                          "pos": np.arange(len(points))})
    earliest = (order.sort_values("year", kind="stable")
                .drop_duplicates(["col", "row_from_south"], keep="first")
                .sort_values(["col", "row_from_south"]))
    return points.iloc[earliest["pos"].to_numpy()].reset_index(drop=True)
