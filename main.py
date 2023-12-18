from datetime import datetime as dt
import os
from thinning import thinning
from distacc import distacc
from optpaths import optpaths

# PARAMETERS ------------------------------------------------------------------
workdir = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse"
presence = "msculpturalis_20230925"  # file and layer name (without extension) of input presence point data, expected in GPKG format
cost = "msculpturalis_sdm_clip_rev_scaled100.tif"  # input cost raster     msculpturalis_sdm_clip_rev     _rescaled100   _scaled100   costs_with_barriers
run = "sdmrev100"  # output names will be prefixed {presence}_{run} and existing files/layers overwritten.    sdmrev100   sdmrev  costrast1   simple100
year_field = "observation_year"  # field in presence data containing observation year
start_year = 2008  # year of first observation, or first year of analysis
end_year = 2023  # year of latest observation, or last year of analysis  # tbd: input = output does not work
# -----------------------------------------------------------------------------

# tbd: read data here and pass to functions

# Execute scripts
thinning(workdir, presence, cost, run, year_field)
distacc(presence, cost, run, year_field, start_year, end_year)
optpaths(presence, run, year_field, start_year, end_year)
