# WORK DIRECTORY
# Path where files are read from and written to
workdir_path = r"C:\Users\Christa\Documents\Git\manuscript\data"

# SCRIPT RUN NAME
# Output file names and layers will be prefixed with {run} and existing files/layers with identical name overwritten
run = "imexicana_20241227_gtopo30exp5km_89"

# POPULATION DELINATION
# To isolate populations, we remove least-cost paths that have an accumulated cost exceeding a specified threshold.
# This threshold can be set as a quantile of the accumulated cost distribution. If no threshold is provided, the script
# defaults to the upper outlier fence, calculated as Q3 + 1.5 * IQR.
threshold = 0.89

# PRESENCE / OBSERVATION DATA
# Name of the file, expected in GPKG format, with identical file and layer name
presence_name = "imexicana_20241227.gpkg"
# Field containing observation year, expected in integer format
year_field = "year"
# Free text field intended to contain the location of a point.
# Currently not actually used by this project, but will be included in the output data.
# tbd ungültiger Feldname führt nicht zu Fehler?!
location_field = "countryCode"
# First year to be analyzed (usually the year of the first observation)
start_year = 1993
# Last year to be analyzed (usually the latest completed year of observation)
end_year = 2024

# COST SURFACE
# Name of the file, expected in GeoTIFF format
cost_name = "cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif"
