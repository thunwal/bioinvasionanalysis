# bioinvasionanalysis

## About this project

Understanding how non-native species spread across landscapes is crucial for effective management strategies. 
This Python project aims to support the analysis of the **expansion dynamics of non-native species** by employing a 
data-driven, spatio-temporal approach. Using observation data and a landscape model ("cost surface"),

1. **sequential least-cost modelling** is applied in annual time steps to reconstruct the spread as least-cost paths, 
2. **distinct populations** are delineated by excluding paths with high accumulated cost, and 
3. **expansion rates** are calculated for all delineated populations using the distance regression method.

This repository is published as part of:

> Rohrbach, C., Wallentin, G., Bila Dubaić, J., & Lanner, J. (2025).
> Leveraging sequential least-cost modelling to uncover multiple introductions:
> a case study of an invasive wild bee species. *Landscape Ecology*, 40(8). 
> [https://doi.org/10.1007/s10980-025-02188-9](https://doi.org/10.1007/s10980-025-02188-9)

## Project structure

To analyze your data, you may use the provided [Jupyter notebook](notebooks/bioinvasionanalysis_demo.ipynb)
or run `main.py`. We recommend using the notebook to familiarize yourself with the project.
Either way you may want to start with the included demo data and default parameters to get your first results.

The demo data consists of European [observation data](data/imexicana_20241227.gpkg) for the
[Mexican grass-carrying wasp](https://en.wikipedia.org/wiki/Isodontia_mexicana)
retrieved from GBIF ([source](https://doi.org/10.15468/dl.jm6bhs)), 
and a very basic [cost surface](data/cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif) derived from the GTOPO30 DEM by USGS
([source](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-global-30-arc-second-elevation-gtopo30)).

## Workflow

0. **Prepare input data** *(only if you intend to analyze your own data)*
   - See chapter "Input data requirements"
1. **Run the analysis**  
   - **a) using the Jupyter notebook**, see chapter "Running the Jupyter notebook"  
   - **b) or by running the script**, see chapter "Running the script"
2. **Work with the results in your favourite tools**
   - `{run}.gpkg` Least-cost paths and observation data assigned to populations (GPKG file)
   - `{run}_cumulative_distances.csv` Cumulative distances for all populations and years (CSV file)
   - `{run}_expansion_rates.csv` Expansion rates for all populations (CSV file)
   - `{run}_sensitivity_test.csv` Sensitivity test (effect of parameters on results) (CSV file)

## Project setup

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

## Running the Jupyter notebook

1. Start the notebook server. Enter the following in the terminal: 
   ```bash
   jupyter notebook
   ```
2. A new browser tab should open. Open the folder `notebooks` and click `bioinvasionanalysis_demo.ipynb`.
3. Follow the instructions given in the notebook.

## Running the script

1. Check the parameters in `params.py`. 
2. Refer to the comments in `params.py` for explanations on the parameters.
3. Run the `main.py` script. Enter the following in the terminal:
   ```bash
   python c:\path\to\myprojects\bioinvasionanalysis\main.py
   ```

## Input data requirements

Note: The observation data are automatically projected to the coordinate reference system of the cost surface.

- **Observation data**:  
   Format: Point data (GeoPackage, *.GPKG)  
   The layer name must match the file name.  
   Required fields (field names can be configured in `params.py`):  
   - Observation year (integer), e.g. 2020
   - Name or code of location (string), e.g. "Austria" or "Vienna, AT"
   - Point geometry
<br><br>
- **Cost surface**:  
  Format: Raster (GeoTIFF, *.TIF)  
  The values represent the cost of moving through the landscape.  
  Note that the cells must have equal side lengths.

## Development ideas

- automatic detection of first and last observation year
- add the sensitivity test to the Jupyter notebook
- enhance Jupyter notebook with interactive maps
- retrieve observation data for a given species from the GBIF API
- open to community suggestions and contributions
