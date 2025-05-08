from datetime import datetime as dt
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon, box


def thin(in_gpkg, in_points, in_cost, out_gpkg, out_points, out_points_thinned, year_field, start_year, end_year, location_field):
    """
    Prepares presence data for further processing by projecting it to the cost surface CRS and reducing the
    data to the resolution of the cost surface, retaining the earliest observation per cell.
    """
    extent = in_cost.bounds
    xmin, ymin, xmax, ymax = extent.left, extent.bottom, extent.right, extent.top
    cell_size, cell_size_y = in_cost.res
    crs_code = in_cost.crs
    print(f"[{dt.now().strftime('%H:%M:%S')}] Cost raster has CRS {crs_code} and cell size {cell_size} x {cell_size_y}.")

    # Check if cell size width and height are the same. If not, stop script execution.
    # The thinning process relies on a fishnet with equal cell side length.
    if cell_size != cell_size_y:
        raise Exception("Raster cells are required to have equal side lengths for the thinning procedure.")

    # Read presence data. Import the columns specified in year_field and location_field only
    print(f"[{dt.now().strftime('%H:%M:%S')}] Loading presence data from '{in_gpkg}'...")
    points = gpd.read_file(in_gpkg, layer=in_points, include_fields=[year_field,location_field])
    print(f"[{dt.now().strftime('%H:%M:%S')}] Presence data has CRS {points.crs} and {len(points.index)} rows, "
        f"of which {len(points.dropna(subset=[year_field, 'geometry']).index)} rows with non-null year and geometry.")
    points = points.dropna(subset=[year_field, 'geometry']).astype({year_field: 'int32'})
    points = points[(points[year_field] >= start_year) & (points[year_field] <= end_year)]

    # Sample 80% of the data randomly (tbd - for testing - remove later?)
    # sample_fraction = 0.8
    # points = points.sample(frac=sample_fraction, random_state=None)
    # print(f"[{dt.now().strftime('%H:%M:%S')}] Randomly sampled {sample_fraction * 100}% of points, resulting in {len(points.index)} rows.")

    # Reproject points to match the coordinate system of the raster
    try:
        points = points.to_crs(crs_code)
        print(f"[{dt.now().strftime('%H:%M:%S')}] Projected presence data to {crs_code}.")
    except Exception as e:
        raise Exception(f"[{dt.now().strftime('%H:%M:%S')}] Failed to project presence data to {crs_code}.") from e

    # Filter points to match the extent of the raster
    raster_bbox = box(xmin, ymin, xmax, ymax)
    points = points[points.geometry.within(raster_bbox)]
    print(f"[{dt.now().strftime('%H:%M:%S')}] Applied filter to include presence data within raster extent only.")

    # Save the imported points to the GeoPackage which is specific to the script run
    points.to_file(out_gpkg, layer=out_points)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Imported presence data saved to '{out_gpkg}', layer '{out_points}'.")

    # Create a temporary fishnet based on the raster properties
    print(f"[{dt.now().strftime('%H:%M:%S')}] Creating temporary fishnet with raster properties...")
    x_range = np.arange(xmin, xmax, cell_size)
    y_range = np.arange(ymin, ymax, cell_size)

    fishnet = gpd.GeoDataFrame(geometry=[Polygon([
        (x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)
    ]) for x in x_range for y in y_range])

    fishnet.set_crs(crs_code, inplace=True)

    # Join points with fishnet cells
    print(f"[{dt.now().strftime('%H:%M:%S')}] Joining observations and fishnet polygons...")
    thinned = gpd.sjoin(points, fishnet, how="inner", predicate="intersects")

    # Group points by fishnet cell and select the point with the minimum year in each group
    print(f"[{dt.now().strftime('%H:%M:%S')}] Selecting earliest observation per fishnet polygon...")
    thinned = thinned.groupby("index_right").apply(lambda group: group.loc[group[year_field].idxmin()])

    # Drop index and reset CRS (CRS information gets lost during sjoin or groupby)
    thinned.reset_index(drop=True, inplace=True)
    thinned.drop(columns=['index_right'], inplace=True)
    thinned.set_crs(crs_code, inplace=True)

    # Save the thinned points to the GeoPackage which is specific to the script run
    thinned.to_file(out_gpkg, layer=out_points_thinned)
    print(f"[{dt.now().strftime('%H:%M:%S')}] Thinned imported presence data saved to '{out_gpkg}', layer '{out_points_thinned}'.")

    return thinned, cell_size
