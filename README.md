# bioinvasionanalysis

> [!NOTE]  
> This project is currently in an early development phase.

## What is this project about?

In its final version, this script will enable you to (subject to change!):
- BETA - Reconstruct possible dispersal pathways of a non-native species using cost accumulation and least-cost path analysis.
- TBD - Isolate potentially independent populations by eliminating the most costly pathways, assuming such represent jump dispersal or bridge different introduction events.
- TBD - Calculate the annual expansion rate for each population as cumulative distance to the first record in the respective population.
- TBD? - Model annual dispersal areas using cost accumulation and the previously calculated expansion rates and extrapolate future expansion.

## Environment setup in PyCharm

### If only the open-source workflow is to be used

Create your own environment as you like.  
Make sure to install needed packages as to per the ```requirements.txt``` file.

### If the ArcGIS Pro workflow is to be used

Clone the default arcgispro-py3 environment because it is not possible to install packages to the default 
environment. Follow [these](https://pro.arcgis.com/en/pro-app/3.0/arcpy/get-started/clone-an-environment.htm) steps.

Add Python.exe from the newly created path as the project interpreter via 
```Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter > Virtualenv environment > Existing```.

Install required packages using ```Settings > Project > Python Interpreter``` as to per the ```requirements.txt``` file.

## Prepare input data

The following data is needed to run this script:

- Presence data as point data in GPKG format with an attribute containing the year of observation.
- Cost raster in GeoTIFF format containing the cost of moving through each cell.
  - The raster should be created with an equal-area projection and square cells so that the true distance from cell to cell remains the
    same throughout the raster. (?)
  - If the effects of different cost raster inputs are to be compared, you should rescale them to a shared scale. 
    To rescale to a scale of e.g. 1-100 you may use the following Map Algebra:  
    ``` ((raster - raster.min) * 99 / (raster.max - raster.min)) + 1 ```

## Run script

Enter your parameters in the first code block of ```main.py``` and run the script.

Parameters:

```workdir_path``` Working directory where input is loaded from and output is written to.  
```presence_name``` File and layer name of your presence point data (GPKG).  
```cost_name``` File name of your cost raster (GeoTIFF).  
```run``` Distinct name for the script run. Existing data with the same name will be overwritten.  
```year_field``` Name of the presence data field containing the observation year.  
```start_year``` First year to be included in the analysis.  
```end_year``` Last year to be included in the analysis.  
