# WORK DIRECTORY
# Path where files are read from and written to
workdir_path = r"C:\Users\this is me\Documents\bioinvasionanalysis-data"

# SCRIPT RUN NAME
# Output file names and layers will be prefixed with {run} and existing files/layers with identical name overwritten
run = "msculp20241203_2024_inv_scaled_95"

# POPULATION DELINATION
# To isolate populations, we remove least-cost paths that have an accumulated cost exceeding a specified threshold.
# This threshold can be set as a quantile of the accumulated cost distribution. If no threshold is provided, the script
# defaults to the upper outlier fence, calculated as Q3 + 1.5 * IQR.
threshold = 0.95

# PRESENCE / OBSERVATION DATA
# Name of the file, expected in GPKG format, with identical file and layer name
presence_name = "msculpturalis_20241203.gpkg"
# Field containing observation year, expected in integer format
year_field = "observation_year"
# Free text field intended to contain the location of a point.
# Currently not actually used by this project, but will be included in the output data.
location_field = "country"
# First year to be analyzed (usually the year of the first observation)
start_year = 2008
# Last year to be analyzed (usually the latest completed year of observation)
end_year = 2024

# COST SURFACE
# Name of the file, expected in GeoTIFF format
cost_name = "sdm_inverted_scaled-0-1.tif"
