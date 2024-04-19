# bioinvasionanalysis

> [!NOTE]\
> This project is under development.


## About this project

This script is intended to support the analysis of the spatio-temporal dispersal dynamics of a non-native species.
Given a cost raster and presence point data, it enables you to:

- Reconstruct possible dispersal pathways.
- Isolate potentially independent populations.
- (work in progress) Calculate the annual expansion rate for each population.

After thinning the presence data to the raster resolution, the script creates sequential least-cost paths 
connecting each presence point with the least costly to reach presence point which was known in the previous year. 

The costliest paths are subsequently removed to isolate groups of connected paths and points, and for each group of 
presence points, the expansion rate is calculated by regressing accumulated distance against time.


## Future development

- Finish expansion rate calculation
- Real script parametrization
- Parameter to choose between open-source and ArcPy least-cost modelling


## Setting up the environment

The following explanations refer to PyCharm Community Edition.

### If you only use the open-source part:

Create your own environment as you like. Make sure to install needed packages as to per the `requirements.txt` file.

### If you use the ArcPy part:

Clone the default `arcgispro-py3` environment as it is not possible to install packages to the default environment. 
Follow [these](https://pro.arcgis.com/en/pro-app/3.0/arcpy/get-started/clone-an-environment.htm) steps.

Add `Python.exe` from the newly created environment path as the project interpreter via 
`Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter > Virtualenv environment > Existing`.

Install required packages using `Settings > Project > Python Interpreter` as to per the `requirements.txt` file.


## Input

The following data is needed to run this script:

- Presence data as point data in GPKG format with an attribute containing the year of observation.
- Cost raster in GeoTIFF format containing the cost of moving through each cell.
  - Note that the cells must have a square shape (equal side lengths).


## Output

- `{run}.gpkg` Contains sequential least-cost paths and grouped presence data.
- `{run}_expansion_rates_plot_data.csv` Data needed to regress distance against time.
- `{run}_expansion_rates_results.csv` Expansion rates of all populations.
- `{run}_sensitivity_test` Results after testing cost thresholds to isolate populations.


## Running the script

Enter your parameters in the first code block of `main.py` and run the script.

Parameters:

- `workdir_path` Working directory from where input is loaded from and output is written to.
- `presence_name` File and layer name of your presence point data (GPKG).
- `cost_name` File name of your cost raster (GeoTIFF).
- `run` Distinct name for the script run. Existing data with the same name will be overwritten.
- `year_field` Name of the presence data field containing the observation year.
- `start_year` First year to be included in the analysis.
- `end_year` Last year to be included in the analysis.
