from datetime import datetime as dt
import numpy as np
import geopandas as gpd
from shapely.ops import linemerge, unary_union
from shapely.geometry import LineString, MultiLineString


def subpop(gpkg, lyr_paths, lyr_paths_union, quantile):
    paths = gpd.read_file(gpkg, layer=lyr_paths, driver="GPKG")
    threshold = np.quantile(paths['accumulated_cost'], quantile)
    paths_filtered = paths[paths['accumulated_cost'] < threshold]

    print(f"[{dt.now().strftime('%H:%M:%S')}] Merging paths with a cost lower than {threshold} ({quantile} quantile)...")
    #paths_filtered_union = linemerge(list(paths_filtered.geometry.values))
    #paths_filtered_union_gdf = gpd.GeoDataFrame(geometry=[paths_filtered_union], crs=paths.crs)
    # tbd: something with linemerge (ensure that only touching, but not crossing lines are connected)
    # Idee: Spalte für ID inzufügen, zufälligen Path selektieren, iterativ selektieren über "touch" bis Auswahl nicht mehr wächst,
    # ID ergänzen, dann aus den übrigen Paths wieder zufälligen selektieren, etc

    # Save the selected and tagged paths to the GeoPackage which specific to the script run
    paths_filtered_union_gdf.to_file(gpkg, layer=lyr_paths_union, driver="GPKG")
    print(f"[{dt.now().strftime('%H:%M:%S')}] Merged paths saved to '{gpkg}', layer '{lyr_paths_union}'.")
