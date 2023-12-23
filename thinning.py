from datetime import datetime as dt
import geopandas as gpd
import numpy as np
import os
from shapely.geometry import Polygon

def thinning(workdir_path, presence_name, cost, run, year_field):
    extent = cost.bounds
    xmin, ymin, xmax, ymax = extent.left, extent.bottom, extent.right, extent.top
    cell_size, cell_size_y = cost.res
    crs_code = cost.crs
    print(f"[{dt.now().strftime('%H:%M:%S')}] Cost raster has CRS {crs_code} and cell size {cell_size} x {cell_size_y}.")

    # Check if cell size width and height are the same. If not, stop script execution.
    # The thinning process relies on a fishnet with equal cell side length.
    if cell_size != cell_size_y:
        raise Exception("Raster cells are required to have equal side lengths for the thinning procedure.")

    # Read presence data. Import the column specified in year_field only.
    print(f"[{dt.now().strftime('%H:%M:%S')}] Reading presence data...")
    points = gpd.read_file(os.path.join(workdir_path, f"{presence_name}.gpkg"), driver="GPKG", layer=presence_name, include_fields=[year_field])
    print(f"[{dt.now().strftime('%H:%M:%S')}] Presence data has CRS {points.crs} and {len(points.index)} rows, "
        f"of which {len(points.dropna(subset=[year_field, 'geometry']).index)} rows with non-null year and geometry.")

    # Reproject points to match the coordinate system of the raster.
    try:
        points = points.to_crs(crs_code)
        print(f"[{dt.now().strftime('%H:%M:%S')}] Projected presence data to {crs_code}.")
    except Exception as e:
        raise Exception(f"[{dt.now().strftime('%H:%M:%S')}] Failed to project presence data to {crs_code}.") from e

    # Create a temporary fishnet based on the raster properties
    print(f"[{dt.now().strftime('%H:%M:%S')}] Creating temporary fishnet with raster properties...")
    x_range = np.arange(xmin, xmax, cell_size)
    y_range = np.arange(ymin, ymax, cell_size)

    fishnet = gpd.GeoDataFrame(geometry=[Polygon([
        (x, y), (x + cell_size, y), (x + cell_size, y + cell_size), (x, y + cell_size)
    ]) for x in x_range for y in y_range])

    fishnet.set_crs(crs_code, inplace=True)

    # Join points with fishnet cells
    print(f"[{dt.now().strftime('%H:%M:%S')}] Joining presence data and fishnet polygons...")
    thinned = gpd.sjoin(points, fishnet, how="inner", predicate="intersects")

    # Group points by fishnet cell and select the point with the minimum year in each group
    print(f"[{dt.now().strftime('%H:%M:%S')}] Selecting presence data with minimum year per cell...")
    thinned = thinned.groupby("index_right").apply(lambda group: group.loc[group[year_field].idxmin()])

    # Drop index and reset CRS (CRS information gets lost during sjoin or groupby)
    thinned.reset_index(drop=True, inplace=True)
    thinned.set_crs(crs_code, inplace=True)

    # Save the thinned points to the GeoPackage which specific to the script run
    thinned.to_file(os.path.join(workdir_path, f"{presence_name}_{run}.gpkg"), layer=f"{presence_name}_{run}_thinned", driver="GPKG")
    print(f"[{dt.now().strftime('%H:%M:%S')}] Thinned presence data saved to '{presence_name}_{run}.gpkg', layer '{presence_name}_{run}_thinned'.")

    return thinned
