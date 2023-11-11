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
arcpy.env.extent = ("3127728.32064701 1511542.10363147 6425328.32064701 3369742.10363147 PROJCS[\"ETRS_1989_LAEA\","
                    "GEOGCS[\"GCS_ETRS_1989\",DATUM[\"D_ETRS_1989\",SPHEROID[\"GRS_1980\",6378137.0,298.257222101]],"
                    "PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],"
                    "PROJECTION[\"Lambert_Azimuthal_Equal_Area\"],PARAMETER[\"False_Easting\",4321000.0],"
                    "PARAMETER[\"False_Northing\",3210000.0],PARAMETER[\"Central_Meridian\",10.0],"
                    "PARAMETER[\"Latitude_Of_Origin\",52.0],UNIT[\"Meter\",1.0]]")
arcpy.env.snapRaster = path_cost_surface
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb


def optimalpaths():
    # Check out any necessary licenses.
    try:
        arcpy.CheckOutExtension("spatial")

        # Iterate through the specified range of years
        # start_year + 1 because no paths can be created for first year
        # end_year + 1 because range end is not included in range
        for year in range(start_year + 1, end_year + 1):
            print(f"Processing features for year {year}...")

            # Form the raster names based on the year
            path_dist_acc_raster = fr"{path_gdb}\msculpturalis_{year - 1}_distacc"
            path_back_dir_raster = fr"{path_gdb}\msculpturalis_{year - 1}_backdir"

            # Select features with the current observation year
            arcpy.management.MakeFeatureLayer(path_occurrences, "temp_layer", f"observation_year = {year}")

            # Optimal Path As Line
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"[{current_time}] Calculating optimal paths for year {year}...")
            path_lines = fr"memory\lines"
            arcpy.sa.OptimalPathAsLine("temp_layer", path_dist_acc_raster, path_back_dir_raster, path_lines,
                                       "observation_year", "EACH_CELL", False)

            if not arcpy.Exists(path_target_dataset):
                # Create a new feature class for the first iteration
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"[{current_time}] Create feature class and save lines for year {year}...")
                arcpy.management.CopyFeatures(path_lines, path_target_dataset)
            else:
                # Append to the existing feature class for subsequent iterations
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"[{current_time}] Append lines for year {year}...")
                arcpy.management.Append(inputs=[path_lines], target=path_target_dataset)

            arcpy.Delete_management("temp_layer")
            arcpy.Delete_management(path_lines)

    finally:
        arcpy.CheckInExtension("spatial")


# Call function
optimalpaths()
