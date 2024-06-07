# WORK DIRECTORY
# Path where files are read from and written to
workdir_path = r"C:\Users\Christa\Documents\Example"

# SCRIPT RUN NAME
# Output file names and layers will be prefixed with {run} and existing files/layers with identical name overwritten
run = "msculp20240408_cost1_threshold95"

# POPULATION DELINATION
# To isolate populations, we remove least-cost paths that have an accumulated cost exceeding a specified threshold.
# This threshold can be set as a quantile of the accumulated cost distribution. If no threshold is provided, the script
# defaults to the upper outlier fence, calculated as Q3 + 1.5 * IQR.
threshold = 0.95

# PRESENCE DATA
# Name of the file, expected in GPKG format, with identical file and layer name
presence_name = "msculpturalis_20240408.gpkg"
# Field containing observation year, expected in integer format
year_field = "observation_year"
# Free text field intended to contain the location of a point, but may be used with anything which helps recognize populations
location_field = "country"
# First year to be analyzed (usually the year of the first observation)
start_year = 2008
# Last year to be analyzed (usually the latest completed year of observation)
end_year = 2023

# COST SURFACE
# Name of the file, expected in GeoTIFF format
cost_name = "msculpturalis_cost1.tif"
