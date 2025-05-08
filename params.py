import numpy as np


# ================================================ GENERAL =============================================================
# WORK DIRECTORY
# Path where files are read from and written to
workdir_path = r"C:\Users\Christa\Documents\Git\bioinvasionanalysis\data"

# SCRIPT RUN NAME
# Output file names and layers will be prefixed with {run} and existing files/layers with identical name overwritten
run = "imexicana_20241227_gtopo30exp5km_89"

# EXECUTION MODE
# Controls which parts of the script are executed:
# "analysis": Run analysis only, excluding sensitivity test
# "all": Run analysis and sensitivity test
# "test": Run the sensitivity test only. Prerequisite: Run in analysis mode once to calculate least-cost paths.
mode = "analysis"
# ======================================================================================================================

# ================================================= DATA ===============================================================
# PRESENCE / OBSERVATION DATA
# Name of the file, expected in GPKG format, with identical file and layer name
presence_name = "imexicana_20241227.gpkg"
# Field containing observation year, expected in integer format
year_field = "year"
# Free text field intended to describe the location of a point.
location_field = "countryCode"
# First year to be analyzed (usually the year of the first observation)
start_year = 1993
# Last year to be analyzed (usually the latest completed year of observation)
end_year = 2024

# COST SURFACE
# Name of the file, expected in GeoTIFF format
cost_name = "cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif"
# ======================================================================================================================

# ===================== POPULATION DELINEATION (required for "analysis" and "all" modes) ===============================
# ACCUMULATED COST THRESHOLD
# To isolate populations, we remove least-cost paths that have an accumulated cost exceeding a specified threshold.
# This threshold is defined as a quantile of the accumulated cost distribution. If not specified,
# the script defaults to the upper outlier fence, calculated as Q3 + 1.5 * IQR.
threshold = 0.89  # example for acc. cost value: 4.4 / for quantile value: 0.95
threshold_is_absolute = False  # True = acc. cost value, False = quantile value
# ======================================================================================================================

# ========================== SENSITIVITY TEST (required for "test" and "all" mode) =====================================
# ACCUMULATED COST THRESHOLD RANGE to be tested.
# If not specified, the following test step range will be used: np.arange(0.00, max_cost + 0.01, 0.01)
acc_cost_test_steps = np.arange(9, 10, 0.01)  # example for acc. cost values: np.arange(0.00, 51.00, 0.01) / for quantile values: np.arange(0.85, 0.98, 0.001)
acc_cost_steps_are_absolute = True

# ROBUST POPULATION DEFINITION RANGE to be tested.
# This definition is expressed as the minimum median observation count per year.
# The average expansion rate will be calculated across robust populations.
# If not specified, the following test step range will be used: np.arange(5, 16, 1)
robust_test_steps = np.arange(5, 16, 1)
# ======================================================================================================================
