# bioinvasionanalysis

## About this project

This Python project aims to support the analysis of the **expansion dynamics** of non-native species by employing a 
process-oriented and spatially explicit approach. On the basis of observation data and a cost surface, 
(1) **sequential least-cost modelling** is used to reconstruct the spread with least-cost paths in annual time steps, 
(2) **distinct populations** are delineated by excluding paths with high accumulated cost, and
(3) **expansion rates** are calculated for all delineated populations using the distance regression method. 

This project is published as part of the scientific publication:

> Rohrbach, Christa; Wallentin, Gudrun; Bila Dubaić, Jovana; Lanner, Julia (2024). *Leveraging sequential least-cost 
> modelling to uncover multiple introductions: a case study of an invasive wild bee species.* [in preparation]

## Workflow overview

1. **Input data preparation** *(not part of this project)*  
   - Observation records (GPKG file) and cost surface (GeoTIFF file).  

2. **Define the parameters in `params.py`**  
   - Working directory
   - Input data
   - Analysis period
   - Accumulated cost threshold (expressed as quantile) for population delineation
   - Name for the script run (used to name output files)

3. **Run `main.py`**  
   - This script will run all required modules and generate output files.

4. **Verify the results in your favourite tools**
   - `{run}.gpkg` Least-cost paths and observation data assigned to populations (GPKG file)
   - `{run}_cumulative_distances.csv` Cumulative distances for all populations and years (CSV file)
   - `{run}_expansion_rates.csv` Expansion rates for all populations (CSV file)
   - `{run}_sensitivity_test.csv` Sensitivity test (effect of accumulated cost threshold on number of populations) (CSV file)

For more information on the methodology, please refer to the associated manuscript.

## Future development

- add demo data
- add Jupyter notebook for interactive exploration of results
- add more output fields to the sensitivity test, e.g. the number of observations per population?
- open to community suggestions and contributions

## Input data

- **Observation data**:  
   Format: Point data (GeoPackage, GPKG)  
   For analysis and output, the data will be projected to the coordinate reference system of the cost surface.
   Required fields (field names can be configured in `params.py`):  

   | Field      | Description                      | Example        |  
   |------------|----------------------------------|----------------|  
   | `year`     | Year of observation              | 2020           |  
   | `location` | Name or code of location         | Austria (or: Vienna, AT) |  
   | `geometry` | Point geometry                   | POINT(16.37 48.21) |

- **Cost surface**:
  - Format: Raster (GeoTIFF)
  - The values represent the cost of moving through the landscape.
  - Note that the cells must have equal side lengths.

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

## Running the script

1. Enter your parameters in `params.py`
   - Refer to the explanations in `params.py`.
   - For the first exploratory run, you might want to start with an arbitrary `threshold` of, e.g., 0.95, and then 
     consult the sensitivity test results and the population data to identify a suitable threshold.
2. Run the `main.py` script:
   ```bash
   python c:\path\to\myprojects\bioinvasionanalysis\main.py
   ```
