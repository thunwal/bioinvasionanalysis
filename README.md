# bioinvasionanalysis

## prep work

rescale raster values to 1-100: ((raster - raster.min) * 99 / (raster.max - raster.min)) + 1

## Environment setup in PyCharm

You need to clone the default arcgispro-py3 environment because it is not possible to add packages to the default 
environment. Follow [these](https://pro.arcgis.com/en/pro-app/3.0/arcpy/get-started/clone-an-environment.htm) steps.

Next, add Python.exe in the newly created path as the project interpreter via 
Settings > Project > Python Interpreter > Add Interpreter > Add Local Interpreter > Virtualenv environment > Existing.

Then add the following packages using Settings > Project > Python Interpreter:
- geopandas
- shapely

tbd: arcpy in eigenem Env installieren?