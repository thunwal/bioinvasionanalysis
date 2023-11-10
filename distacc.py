import arcpy
from datetime import datetime

# Input data
path_gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
path_occurrences = fr"{path_gdb}\msculpturalis_occurrence_20230925"
path_cost_surface = fr"{path_gdb}\cost_600m"  # arcpy.Raster(fr"{path_gdb}\cost_600m")
start_year = 2009  # second year of the time range to be analysed
end_year = 2012  # last year of the time range to be analysed

# Environment settings
arcpy.env.extent = ("3127728.32064701 1511542.10363147 6425328.32064701 3369742.10363147 PROJCS[\"ETRS_1989_LAEA\","
                    "GEOGCS[\"GCS_ETRS_1989\",DATUM[\"D_ETRS_1989\",SPHEROID[\"GRS_1980\",6378137.0,298.257222101]],"
                    "PRIMEM[\"Greenwich\",0.0],UNIT[\"Degree\",0.0174532925199433]],"
                    "PROJECTION[\"Lambert_Azimuthal_Equal_Area\"],PARAMETER[\"False_Easting\",4321000.0],"
                    "PARAMETER[\"False_Northing\",3210000.0],PARAMETER[\"Central_Meridian\",10.0],"
                    "PARAMETER[\"Latitude_Of_Origin\",52.0],UNIT[\"Meter\",1.0]]")
arcpy.env.snapRaster = fr"{path_gdb}\cost_600m"
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True
arcpy.env.scratchWorkspace = path_gdb
arcpy.env.workspace = path_gdb


# Function to create Distance Accumulation Surface
def distacc():
    # Check out any necessary licenses.
    arcpy.CheckOutExtension("spatial")

    for year in range(start_year, end_year, 1):
        year_str = str(year)

        # Output paths
        path_known_locations = fr"memory\msculpturalis_before_{year_str}"
        path_dist_acc_raster = fr"{path_gdb}\msculpturalis_{year_str}_distacc"
        path_back_dir_raster = fr"{path_gdb}\msculpturalis_{year_str}_backdir"

        # Select locations known in year
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[{current_time}] Selecting occurrences known before {year_str}...")
        arcpy.analysis.Select(in_features=path_occurrences, out_feature_class=path_known_locations,
                              where_clause=f"observation_year < {year_str}")

        # Distance Accumulation for locations known in year
        # The DistanceAccumulation function returns the DistAcc Raster which needs to be saved in a next step.
        # The BackDir Raster is directly saved by the function.
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[{current_time}] Creating distance accumulation raster for year {year_str}...")
        dist_acc_raster = arcpy.sa.DistanceAccumulation(path_known_locations, "", "",
                                                        path_cost_surface, "", "BINARY 1 -30 30", "", "BINARY 1 45",
                                                        path_back_dir_raster, "", "", "", "",
                                                        "", "", "GEODESIC")
        dist_acc_raster.save(path_dist_acc_raster)


distacc()
