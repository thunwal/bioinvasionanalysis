import arcpy
from datetime import datetime

# Input parameters
start_year = 2008  # year of first observation
end_year = 2023  # year of latest observation, or last year of analysis

# Input data
path_gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_cost_surface = fr"{path_gdb}\costs_with_barriers"
path_target_dataset = fr"{path_gdb}\msculpturalis_all_paths_20230925"

# Environment settings
arcpy.env.snapRaster = path_cost_surface
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb


def optpaths():
    # Check out any necessary licenses.
    try:
        arcpy.CheckOutExtension("spatial")

        # Iterate through the specified range of years.
        # start_year + 1 because no paths can be created in the first year.
        # end_year + 1 because range end is not included in range.
        for idx, year in enumerate(range(start_year + 1, end_year + 1)):

            # Form the input raster paths based on the year. Subtract 1 year because we
            # want to create least-cost paths to occurrences known in the previous year.
            path_dist_acc_raster = fr"{path_gdb}\msculpturalis_{year - 1}_distacc"
            path_back_dir_raster = fr"{path_gdb}\msculpturalis_{year - 1}_backdir"

            # Select occurrences with the respective observation year.
            arcpy.management.MakeFeatureLayer(path_occurrences, "temp_layer", f"observation_year = {year}")

            # Create optimal paths.
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Calculating optimal paths for year {year}...")
            path_optpaths = fr"memory\optpaths"
            arcpy.sa.OptimalPathAsLine("temp_layer", path_dist_acc_raster, path_back_dir_raster, path_optpaths,
                                       "observation_year", "EACH_CELL", False)

            # Create new feature class in first iteration and append in subsequent iterations.
            if idx == 0:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Saving optimal paths for year {year}...")
                arcpy.management.CopyFeatures(path_optpaths, path_target_dataset)
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Appending optimal paths for year {year}...")
                arcpy.management.Append(inputs=[path_optpaths], target=path_target_dataset)

            arcpy.Delete_management("temp_layer")
            arcpy.Delete_management(path_optpaths)

    finally:
        arcpy.CheckInExtension("spatial")


# Call function
optpaths()
