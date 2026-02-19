#This script is not a stand alone file and is called in the Disturbance_Blocks script as part of the ECA Analysis

import arcpy
from arcpy import env
from arcpy.sa import *

def createH60(dem,gdb):
    
    env.workspace = gdb
    env.overwriteOutput = True

    #Assign watershed DEM to the Input data
    watershedDEM = dem

# -------------------------------------------------------------------------------
    # Slice DEM into 100 equal area pieces
    print('Create Slice')
    if arcpy.CheckExtension('Spatial') == 'Available':
        arcpy.AddMessage('Available')
        arcpy.CheckOutExtension('Spatial')
        arcpy.AddMessage('Checked Out')
        numberZones = 100
        outSlice = Slice(watershedDEM, numberZones, "EQUAL_AREA") #if failing here do this step in ArcMap
        arcpy.AddMessage('Sliced')
        outSlice.save("DEM_Slice100")
# -------------------------------------------------------------------------------

    # Turn Slice raster into polygon feature class
    arcpy.AddMessage('Convert Slice into polygon')
    inRaster = 'DEM_Slice100'
    outPoly = 'Slice100_Polygon'

    arcpy.RasterToPolygon_conversion(inRaster, outPoly,"NO_SIMPLIFY","VALUE")

    # Use search cursor to get the total area of the slice
    print('Get total area')
    fields = ['SHAPE@AREA']
    inFc = outPoly
    totalArea = 0

    with arcpy.da.SearchCursor(inFc, fields) as cursor:
        for row in cursor:
            totalArea += row[0]

    #print('Total area:'+ totalArea)
    
    # Add field 'percent'
    print('Add percent field')
    fieldName = 'Percent' 
    arcpy.AddField_management(inFc, fieldName, "DOUBLE")

    # Calculate percent of each slice
    print('Calculate percent')
    expression = "!shape.area!/ {} * 100".format(totalArea)    
    arcpy.CalculateField_management (inFc, fieldName, expression, 'PYTHON_9.3')

    # Sort by grid code decending, this makes it so the layers are properly ordered so we can attain the upper 60 using a cursor in the right order.
    print('sort by gridcode')
    outFeature = 'Slice100_Polygon_Sorted'
    sortField = [['gridcode','Descending']]

    arcpy.Sort_management(inFc, outFeature, sortField)

    # Use the sorted feature to start a running total to 60%, populating a list with the gridcodes
    print('Creating List of slices that make up the upper 60%')
    loopFeature = outFeature
    field = ['gridcode','Percent']

    percentSum = 0
    codeList = []

    with arcpy.da.SearchCursor(loopFeature, field) as cursor:
        for row in cursor:
            percentSum += row[1]
            #60.44% was chosen to allow for slices that are not exctally 1.0% and .45 rounds to .5 and .5 would round to 1, so .44 is the cutoff.
            if percentSum < 60.44:
                codeList.append(row[0])
            if percentSum >= 60.44:
                break

    # Use the list of gridcodes to make a selection of those polygons from the Slice feature
    print('Creating feature out of the upper 60%')
    expression = 'gridcode IN {0}'.format(tuple(codeList))
    fc60 = 'Upper60_Temp'
    fcOut = 'Upper_H60_MultiPolygons'

    arcpy.MakeFeatureLayer_management(loopFeature,fc60,expression)

    # Export the in memory selection to a feature class
    arcpy.management.CopyFeatures(fc60, fcOut)                                                                              #FAILING HERE...OR TAKING FOREVER

    # Dissolve the polygons in the new feature class, this will then represent the upper 60% of the watershed
    finalFc = 'Upper_H60'
    arcpy.Dissolve_management (fcOut, finalFc)

    # Erase upper 60 from the slice to create the lower 40%
    print('Create the lower 40% polygon')
    FullSlice = 'Slice100_Polygon'
    Slice40 = 'Slice100_Polygon_H60_Erased'

    arcpy.Erase_analysis(FullSlice,finalFc, Slice40)

    # Dissolve the lower 40% into one polygon
    inDissolve = Slice40
    outDissolve = "Lower_H40"

    arcpy.Dissolve_management (inDissolve, outDissolve)

    # Turn the lower 40% into a line feature. The reason to do this is bacause the upper 60% will have a line
    # on the outside and inside of the watershed, where the lower 40 will not and the exterior edge represents the same thing.
    print('Create the H60 Line')
    inPoly = outDissolve
    outLine = 'H60_Line'

    arcpy.PolygonToLine_management (inPoly,outLine)

    print('Finished')
    # Completed
