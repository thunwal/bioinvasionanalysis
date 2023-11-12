import arcpy
from datetime import datetime

# Input parameters
start_year = 2008  # year of first observation
end_year = 2023  # year of latest observation, or last year of analysis

# Input data
path_gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_cost_surface = fr"{path_gdb}\costs_with_barriers"

# Environment settings
arcpy.env.snapRaster = path_cost_surface
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb


# Function definition
def distacc():
    # Check out any necessary licenses.
    try:
        arcpy.CheckOutExtension("spatial")

        # Iterate through the specified range of years.
        # end_year + 1 because end of range is not included in range.
        for year in range(start_year, end_year + 1, 1):

            # Form the output raster paths.
            path_dist_acc_raster = fr"{path_gdb}\msculpturalis_{year}_distacc"
            path_back_dir_raster = fr"{path_gdb}\msculpturalis_{year}_backdir"

            # Select occurrences known in the respective year.
            arcpy.management.MakeFeatureLayer(path_occurrences, "temp_layer", f"observation_year <= {year}")

            # Create distance accumulation raster.
            # Note: This function returns the raster which needs to be saved in an extra step.
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating distance accumulation raster for year {year}...")
            dist_acc_raster = arcpy.sa.DistanceAccumulation("temp_layer", "", "",
                                                            path_cost_surface, "", "BINARY 1 -30 30", "", "BINARY 1 45",
                                                            path_back_dir_raster, "", "", "", "",
                                                            "", "", "GEODESIC")
            dist_acc_raster.save(path_dist_acc_raster)
            arcpy.Delete_management("temp_layer")

    finally:
        arcpy.CheckInExtension("spatial")


# Call function
distacc()
