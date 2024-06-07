# bioinvasionanalysis

## About this project
**This project is intended to support the analysis of the spatio-temporal dispersal dynamics of a potentially
multiple-introduced non-native species without prior knowledge of population structure. Given a cost surface and 
presence data, it delineates potentially distinct populations and calculates the expansion rate for each population.**

After thinning the presence data to the raster resolution, retaining the earliest observation per cell, the script
sequentially creates least-cost paths in annual time steps connecting each observation with the nearest earlier
observation based on accumulated cost. High-cost paths are subsequently removed, based on a configurable threshold, to
isolate groups of connected paths and nearby points (populations). For each population, the expansion rate is
calculated by regressing the cumulative distance of observations to the first observation against time.

For the creation of least-cost paths I implement the *Graph* module of the
[scikit-image](https://scikit-image.org/docs/stable/api/skimage.graph.html) package. I also provide an alternative
solution for least-cost modelling based on ArcPy in this repository in the form of the two scripts `arcgis_distacc` and
`arcgis_optpaths`, but these are not yet seamlessly integrated and outcommented for this reason. To use them, a valid
ArcGIS Pro license is required.

## Future development

- Parameter to choose between scikit-image and ArcPy based least-cost modelling?
- Add more sensitivity tests, e.g. for the number of observations per population?
- ...let me know your thoughts!

## Setting up the environment

Create your own environment as you like.
Make sure to install needed packages as to per the `requirements.txt` file (`pip install -f requirements.txt`).

### If you want to use ArcPy scripts:

Clone the default `arcgispro-py3` environment as it is not possible to install packages to the default environment. 
Follow [these](https://pro.arcgis.com/en/pro-app/3.0/arcpy/get-started/clone-an-environment.htm) steps.

PyCharm users may proceed as follows (I can't provide instructions for other IDEs): Add `Python.exe` from the newly
created environment path as the project interpreter via `Settings > Project > Python Interpreter > Add Interpreter > 
Add Local Interpreter > Virtualenv environment > Existing`. Install required packages using `Settings > Project > 
Python Interpreter` as to per the `requirements.txt` file.

## Input

- Presence point data in GPKG format containing the year and place name of observation.
- Cost surface in GeoTIFF format representing the cost of moving through each cell.
  - Note that the cells must have a square shape (equal side lengths).

## Output

- `{run}.gpkg` Sequential least-cost paths and presence data assigned to populations.
- `{run}_cumulative_distances.csv` Cumulative distances per year for all populations.
- `{run}_expansion_rates.csv` Expansion rates for all populations.
- `{run}_sensitivity_test.csv` Sensitivity test of the threshold's effect on the number of populations.

## Running the script

Enter your parameters in `params.py` and run the `main.py` script.
