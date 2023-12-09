# bioinvasionanalysis

## Prepare input data

The following data is needed to run this script:

- Point data with an attribute containing the year of observation.
- Cost raster (aka friction raster) with square cells containing the cost of moving in space.
  - If multiple cost rasters are to be compared, you should normalize them. For example to a scale of 1-100 using
    Raster Calculator and the following Map Algebra:  
    ``` ((raster - raster.min) * 99 / (raster.max - raster.min)) + 1 ```

## Environment setup in PyCharm

Clone the default arcgispro-py3 environment because it is not possible to install packages to the default 
environment. Follow [these](https://pro.arcgis.com/en/pro-app/3.0/arcpy/get-started/clone-an-environment.htm) steps.

Add Python.exe from the newly created path as the project interpreter via 
Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter > Virtualenv environment > Existing.

Install the following additional packages using Settings > Project > Python Interpreter:
- geopandas
- shapely
