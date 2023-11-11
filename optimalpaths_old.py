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

        # Iterate through all point features
        with arcpy.da.SearchCursor(path_occurrences, ['SHAPE@', 'OID@', 'observation_year']) as cursor:
            for idx, row in enumerate(cursor):
                point_geometry, object_id, year = row

                if year == start_year:
                    print(f"Skipping feature {object_id} because its observation year is equal to the start year.")
                    continue

                # Form the raster names based on the year. Subtract 1 year because we want to create the
                # least-cost path to an occurrence known in the previous year.
                path_dist_acc_raster = fr"{path_gdb}\msculpturalis_{year - 1}_distacc"
                path_back_dir_raster = fr"{path_gdb}\msculpturalis_{year - 1}_backdir"

                # Optimal Path As Line
                current_time = datetime.now().strftime("%H:%M:%S")
                print(f"[{current_time}] Calculating optimal path for feature {object_id} in year {year}...")
                path_line = fr"memory\line"  # msculpturalis_line_{year}_{object_id}_optimalpath
                arcpy.sa.OptimalPathAsLine(point_geometry, path_dist_acc_raster, path_back_dir_raster, path_line,
                                           "", "BEST_SINGLE", False)

                if idx == 0:
                    # Create a new feature class in the first iteration
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"[{current_time}] Create feature class and save line for feature {object_id}...")
                    arcpy.management.CopyFeatures(path_line, path_target_dataset)
                else:
                    # Append to the existing feature class for subsequent iterations
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"[{current_time}] Append line for feature {object_id}...")
                    arcpy.management.Append(inputs=[path_line], target=path_target_dataset)

                arcpy.Delete_management(path_line)

    finally:
        arcpy.CheckInExtension("spatial")


# Call function
optimalpaths()
