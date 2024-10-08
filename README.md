# bioinvasionanalysis

## About this project
This Python project is designed to support the analysis of the spatio-temporal dispersal dynamics of a species spreading 
outside of its native range and uncover multiple introductions. Given a cost surface and presence data, it delineates 
potentially distinct populations and calculates the expansion rate for each population.

The scripts performs the following steps:

1. **Spatial thinning** of the presence data, retaining the earliest observation per cost surface cell
2. **Sequential least-cost modelling**, connecting each observation with the nearest earlier observation via least-cost path
3. **Delineate populations** by removing high-cost paths from the result set, thus isolating groups of paths and points
4. **Calculate expansion rates** for all populations using the distance regression method

For creating least-cost paths, the *Graph* module from the
[scikit-image](https://scikit-image.org/docs/stable/api/skimage.graph.html) package is used.

## Future development

- add demo data
- add Jupyter notebook which supports the evaluation of results
- add more output fields to the sensitivity test, e.g. the number of observations per population?
- open to community suggestions and contributions

## Getting started

1. **Clone the repository**  
   On Windows:
    ```bash
    cd c:\path\to\myprojects  # path were you want to save bioinvasionanalysis
    git clone https://github.com/thunwal/bioinvasionanalysis.git  # downloads the repository
    ```

2. **Create a virtual environment**  
    On Windows:
    ```bash
    cd c:\path\to\myenvs  # path where you want to create the environment
    python -m venv venv_bioinv  # creates an environment "venv_bioinv"
    venv_bioinv\Scripts\activate  # activates the enviornment "venv_bioinv"
    ```

3. **Install required packages**  
    On Windows:
    ```bash
    cd c:\path\to\myprojects\bioinvasionanalysis  # navigate to the repository
    python -m pip install -r requirements.txt  # this text file contains the packages to be installed
    ```

## Input

- **Presence point data** in GPKG format containing the year and place name of observation.
- **Cost surface** in GeoTIFF format representing the cost of moving through each cell.
  - Note that the cells must have equal side lengths.

## Output

- `{run}.gpkg` Sequential least-cost paths and presence data assigned to populations.
- `{run}_cumulative_distances.csv` Cumulative distances per year for all populations.
- `{run}_expansion_rates.csv` Expansion rates for all populations.
- `{run}_sensitivity_test.csv` Sensitivity test of the threshold's effect on the number of populations.

## Running the script

1. Enter your parameters in `params.py`
2. Run the `main.py` script:
   ```bash
   python c:\path\to\myprojects\bioinvasionanalysis\main.py
   ```
