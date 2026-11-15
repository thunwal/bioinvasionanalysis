import numpy as np


# ================================================ GENERAL =============================================================
# WORK DIRECTORY
# Path where files are read from and written to
workdir_path = r"/home/christa/Git/bioinvasionanalysis/data/"

# SCRIPT RUN NAME
# Output file names and layers will be prefixed with {run} and existing files/layers with identical name overwritten
run = "vvelutina_gtopo30exp5km"

# EXECUTION MODE
# Controls which parts of the script are executed:
# "analysis": Run analysis only, excluding sensitivity test
# "all": Run analysis and sensitivity test
# "test": Run the sensitivity test only. Prerequisite: Run in analysis mode once to calculate least-cost paths.
mode = "test"
# ======================================================================================================================

# ================================================= DATA ===============================================================
# PRESENCE / OBSERVATION DATA
# Source of the observation data:
# "file": use your own GPKG file (see presence_name, year_field, location_field)
# "inaturalist": download observations from iNaturalist (see section INATURALIST below)
presence_source = "inaturalist"
# Name of the file, expected in GPKG format, with identical file and layer name.
# For presence_source = "inaturalist", the download is saved under this name.
presence_name = "vvelutina_20261113.gpkg"
# Field containing observation year, expected in integer format (ignored for iNaturalist: "year")
year_field = "year"
# Free text field intended to describe the location of a point (ignored for iNaturalist: "country")
location_field = "countryCode"
# First year to be analyzed (usually the year of the first observation). None = earliest year in the data
start_year = None
# Last year to be analyzed (usually the latest completed year of observation). None = latest year in the data
end_year = None

# INATURALIST (only used for presence_source = "inaturalist")
# Observations are downloaded for the extent of the cost surface and the years start_year to end_year.
# The download is reused for further runs as long as presence_name exists, unless inat_refresh = True.
inat_taxon = "Vespa velutina"  # scientific name or iNaturalist taxon ID
inat_quality_grade = "research"  # "research", "needs_id", "casual", or combinations such as "research,needs_id"
# Obscured observations have coordinates randomised by up to ~20 km (privacy, protected species). Recommended: True
inat_exclude_obscured = False
# Exclude observations with a positional accuracy worse than this value in metres. None = cell size of cost surface
inat_max_positional_accuracy = None
inat_refresh = False

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

# ============================================= ANIMATION (animate.py) =================================================
# Renders the results of the run defined above as an animated map: least-cost paths grow towards their destination
# observation, which appears as soon as it is reached. Requires a completed run in "analysis" or "all" mode.

# ROBUST POPULATION DEFINITION
# Populations with a median observation count per year above this value are coloured, all others are grey.
robust_definition = 10

# BASEMAP
# "relief": light grey shaded relief (Esri) with light blue water bodies and country borders (Natural Earth).
# Alternatively, any provider name from xyzservices (https://xyzservices.readthedocs.io), e.g. "Esri.WorldGrayCanvas",
# "Esri.WorldTerrain", "OpenStreetMap.Mapnik", "OpenTopoMap".
# Tiles are downloaded for the map extent and warped to the CRS of the data automatically.
basemap = "relief"
basemap_zoom = "auto"  # "auto" matches the tile resolution to the video width, or an integer zoom level
# Only used for basemap = "relief":
relief_strength = 1.0  # contrast of the relief shading (0 = flat, 1 = default, 2 = strong)
water_colour = "#dce9f2"
border_colour = "#9a9a9a"

# MAP CRS
# None keeps the CRS of the analysis (e.g. ESRI:102031). Any other CRS, e.g. "EPSG:3857", reprojects the data.
map_crs = None

# DISPLAY FILTER (does not affect the analysis)
# Hides paths longer than this value in km, e.g. 300. None shows all paths of the population delineation.
max_path_length_km = None

# OUTPUT
animation_file = f"{run}_animation.mp4"  # ".mp4" (requires ffmpeg) or ".gif"
animation_title = ""  # e.g. "Megachile sculpturalis in Europe"
fps = 30
seconds_per_year = 3.0
hold_start = 1.0  # seconds showing the first year before the animation starts
hold_end = 3.0  # seconds showing the final state
width_px, height_px = 1920, 1080

# PATH GROWTH
# Share of each year during which paths grow (the remainder shows the year's final state).
grow_window = 0.75
# Growth duration relative to path length within a year: 1 = constant speed (long paths take the whole window,
# short ones finish almost instantly), 0 = all paths take the same time, 0.5 = compromise.
duration_exponent = 0.5

# PREVIEW
# Set to a (fractional) year, e.g. 2019.4, to render a single PNG frame instead of the video. Useful to check the
# layout quickly. None renders the video.
preview_year = None
# ======================================================================================================================
