import arcpy
from datetime import datetime as dt
import os
from thinning import thinning
from distacc import distacc
from optpaths import optpaths

# PARAMETERS ------------------------------------------------------------------
gdb = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\p_distanzanalyse.gdb"
workdir = os.path.dirname(gdb)
presence = "msculpturalis_20230925"  # input presence point data
cost = "msculpturalis_sdm_clip_rev_scaled100"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100   _scaled100   costs_with_barriers
run = "sdmrev100"  # output names will be prefixed {presence}_{run} and existing files/layers overwritten.    sdmrev100   sdmrev  costrast1   simple100
year_field = "observation_year"  # field in presence data containing observation year
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: input = output does not work
# -----------------------------------------------------------------------------

# ArcPy environment settings
arcpy.env.snapRaster = os.path.join(gdb, cost)
arcpy.env.parallelProcessingFactor = "100%"
arcpy.env.overwriteOutput = True
arcpy.env.addOutputsToMap = False
arcpy.env.autoCancelling = True

# Read raster properties. Using ArcPy to support File GeoDatabase.
print(f"[{dt.now().strftime('%H:%M:%S')}] Reading raster properties...")
desc = arcpy.Describe(os.path.join(gdb, cost))
arcpy.env.outputCoordinateSystem = desc.spatialReference

# Execute scripts
thinning(gdb, workdir, presence, run, year_field, desc)
distacc(gdb, presence, cost, run, year_field, start_year, end_year)
optpaths(gdb, presence, run, year_field, start_year, end_year)
