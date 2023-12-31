from skimage.graph import route_through_array
import numpy as np
import rasterio as rio


def raster2array(rasterfn):
    raster = rio.open(rasterfn)
    # Read cost raster as array
    array = raster.read(1, masked=True)
    # Identify NoData cells
    nodata_mask = np.ma.getmask(array)
    # Set NoData cells to np.inf
    array[nodata_mask] = np.inf

    return array

def coord2pixelOffset(rasterfn,x,y):
    raster = rio.open(rasterfn)
    geotransform = raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    xOffset = int((x - originX)/pixelWidth)
    yOffset = int((y - originY)/pixelHeight)
    return xOffset,yOffset

def createPath(CostSurfacefn,costSurfaceArray,startCoord,stopCoord):

    # coordinates to array index
    startCoordX = startCoord[0]
    startCoordY = startCoord[1]
    startIndexX,startIndexY = coord2pixelOffset(CostSurfacefn,startCoordX,startCoordY)

    stopCoordX = stopCoord[0]
    stopCoordY = stopCoord[1]
    stopIndexX,stopIndexY = coord2pixelOffset(CostSurfacefn,stopCoordX,stopCoordY)

    # create path
    indices, weight = route_through_array(costSurfaceArray, (startIndexY,startIndexX), (stopIndexY,stopIndexX),geometric=True,fully_connected=True)
    indices = np.array(indices).T
    path = np.zeros_like(costSurfaceArray)
    path[indices[0], indices[1]] = 1
    return path

def array2raster(newRasterfn,rasterfn,array):
    raster = gdal.Open(rasterfn)
    geotransform = raster.GetGeoTransform()
    originX = geotransform[0]
    originY = geotransform[3]
    pixelWidth = geotransform[1]
    pixelHeight = geotransform[5]
    cols = array.shape[1]
    rows = array.shape[0]

    driver = gdal.GetDriverByName('GTiff')
    outRaster = driver.Create(newRasterfn, cols, rows, 1, gdal.GDT_Byte)
    outRaster.SetGeoTransform((originX, pixelWidth, 0, originY, 0, pixelHeight))
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(array)
    outRasterSRS = osr.SpatialReference()
    outRasterSRS.ImportFromWkt(raster.GetProjectionRef())
    outRaster.SetProjection(outRasterSRS.ExportToWkt())
    outband.FlushCache()

def main(CostSurfacefn,outputPathfn,startCoord,stopCoord):

    costSurfaceArray = raster2array(CostSurfacefn) # creates array from cost surface raster

    pathArray = createPath(CostSurfacefn,costSurfaceArray,startCoord,stopCoord) # creates path array

    array2raster(outputPathfn,CostSurfacefn,pathArray) # converts path array to raster


if __name__ == "__main__":
    CostSurfacefn = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\msculpturalis_sdm_clip_rev_scaled100.tif"
    startCoord = (678884.82, 5441740.79)
    stopCoord = (454359.45, 5161896.016)
    outputPathfn = r"C:\Daten\Dokumente\UNIGIS\ArcGIS Projekte\p_distanzanalyse\test.tif"
    main(CostSurfacefn,outputPathfn,startCoord,stopCoord)