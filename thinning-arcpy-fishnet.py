import arcpy
from datetime import datetime

# Input data
path_gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_occurrences_thinned = fr"{path_occurrences}_thinned"
path_cost_surface = fr"{path_gdb}\costs_with_barriers"
path_target_dataset = fr"{path_gdb}\msculpturalis_all_paths_20230925"
desc = arcpy.Describe(path_cost_surface)

# Environment settings
arcpy.env.snapRaster = path_cost_surface
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb
arcpy.env.outputCoordinateSystem = desc.spatialReference

# Create a fishnet based on raster characteristics
print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating fishnet...")
fishnet_path = fr"{path_gdb}\fishnet"  # memory workspace does not support indices

# arcpy.management.CreateFishnet(
#     fishnet_path,
#     str(desc.extent.lowerLeft),
#     str(desc.extent.XMin) + " " + str(desc.extent.YMax),
#     str(desc.meanCellWidth),
#     str(desc.meanCellHeight),
#     0, 0,  # Number of rows and columns (0 means calculate based on the extent)
#     str(desc.extent.upperRight),
#     "NO_LABELS", "#", "POLYGON"
# )
#
# # Create a spatial index for the fishnet feature class
# arcpy.management.AddSpatialIndex(fishnet_path)

# Perform a spatial join between the fishnet and points
print(f"[{datetime.now().strftime('%H:%M:%S')}] Joining occurrences with fishnet...")
spatial_join_result = arcpy.analysis.SpatialJoin(fishnet_path, path_occurrences, fr"{path_gdb}\spatial_join_temp")

# Use the Summary Statistics tool to find the minimum observation_year for each fishnet cell
print(f"[{datetime.now().strftime('%H:%M:%S')}] Extract minimum year per fishnet cell...")
summary_table = fr"{path_gdb}\summary_table"  # r"memory\summary_table.dbf"
arcpy.analysis.Statistics(spatial_join_result, summary_table, [["observation_year", "MIN"]], "OID")

# Create a dictionary to store the minimum observation_year for each fishnet cell
min_observation_years = {}
with arcpy.da.SearchCursor(summary_table, ['OID', 'MIN_observation_year']) as cursor:
    for row in cursor:
        fishnet_id, min_observation_year = row
        min_observation_years[fishnet_id] = min_observation_year

# Create a where clause to select points with the minimum observation_year for each fishnet cell
where_clause = " OR ".join([f"(OID = {fishnet_id} AND observation_year = {min_observation_years[fishnet_id]})" for fishnet_id in min_observation_years])

# Make a layer from the input points and apply the where clause
print(f"[{datetime.now().strftime('%H:%M:%S')}] Selecting points with minimum year per cell...")
arcpy.MakeFeatureLayer_management(path_occurrences, "temp_layer")
arcpy.SelectLayerByAttribute_management("temp_layer", "NEW_SELECTION", where_clause)

# Copy the selected features to the output feature class
arcpy.CopyFeatures_management("temp_layer", path_occurrences_thinned)

# Clean up temporary files
# arcpy.Delete_management(r"memory\spatial_join_temp")
# arcpy.Delete_management(summary_table)
# arcpy.Delete_management(fishnet_path)
arcpy.Delete_management("temp_layer")

print("Thinning process completed.")
