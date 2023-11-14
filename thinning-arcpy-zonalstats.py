import arcpy
from arcpy.sa import ZonalStatisticsAsTable

# Set up workspace and environment settings
arcpy.env.workspace = r"C:\path\to\your\geodatabase.gdb"
arcpy.env.overwriteOutput = True

# Input point feature dataset
input_points = "your_point_feature_class"

# Raster dataset
raster_dataset = "your_raster"

# Output thinned point feature class
output_points = "thinned_points"

# Perform zonal statistics to get the minimum observation_year for each raster cell
zonal_table = "in_memory/zonal_stats_table.dbf"
ZonalStatisticsAsTable(raster_dataset, "VALUE", input_points, zonal_table, "DATA", "MINIMUM")

# Create a dictionary to store the minimum observation_year for each raster cell
min_observation_years = {}
with arcpy.da.SearchCursor(zonal_table, ['VALUE', 'MIN_OBSERVATION_YEAR']) as cursor:
    for row in cursor:
        cell_value, min_observation_year = row
        min_observation_years[cell_value] = min_observation_year

# Create a where clause to select points with the minimum observation_year for each raster cell
where_clause = " OR ".join([f"(RASTERVALU = {cell_value} AND observation_year = {min_observation_years[cell_value]})" for cell_value in min_observation_years])

# Make a layer from the input points and apply the where clause
arcpy.MakeFeatureLayer_management(input_points, "lyr")
arcpy.SelectLayerByAttribute_management("lyr", "NEW_SELECTION", where_clause)

# Copy the selected features to the output feature class
arcpy.CopyFeatures_management("lyr", output_points)

# Clean up temporary files
arcpy.Delete_management(zonal_table)

print("Thinning process completed.")
