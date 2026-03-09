import arcpy, pathlib, os, sys,csv
from pathlib import Path
from arcpy import env
from arcpy.sa import *

#-------------------------------------------------------------------------Base Funcitons -------------------------------------------------------------------------------------------
def clip(inFc,watershedFc,outFc,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    arcpy.analysis.PairwiseClip(inFc, watershedFc, outFc)

def makeFeatureLayer(inFc,outFc,expression,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    arcpy.MakeFeatureLayer_management(inFc,outFc,expression)

def erase(inFc,eraseFc,outFc,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    arcpy.analysis.Erase(inFc,eraseFc,outFc)

def merge(inFcList,outFc,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    arcpy.management.Merge(inFcList,outFc)

def buffer(inFc,outFc,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    distance = '5 Meters'
    arcpy.analysis.PairwiseBuffer(inFc, outFc, distance,'ALL')

def identity(inFc,inident,outFc,gdb):
    env.workspace = gdb
    env.overwriteOutput = True

    arcpy.analysis.Identity(inFc,inident, outFc)

def addField(inFc,inField,fieldType,gdb):
    env.workspace = gdb
    env.overwriteOutput = True
    
    arcpy.management.AddField(inFc,inField,fieldType)

def delete(gdb):
    env.workspace = gdb
    featureList = arcpy.ListFeatureClasses()

    #arcpy.AddMessage(featureList)
    featureNameList = []
    for fc in featureList:
        desc = arcpy.Describe(fc)
        FCname = desc.name
        featureNameList.append(FCname)

    keepFeatures = ['H60_Line','Lower_H40','Upper_H60','ECA_DisturbanceLayer']

    #arcpy.AddMessage(featureNameList)
    deleteList = [x for x in featureNameList if x not in keepFeatures]
    
    deleteList.append('DEM_Slice100')

    arcpy.AddMessage('Deleting:')
    arcpy.AddMessage(deleteList)
    
    for feature in deleteList:
        #fullFc = os.path.join(gdb,feature)
        arcpy.management.Delete(feature)

#-----------------------------------------------------------------Created Disturbance Layers----------------------------------------------------------------------------------------
def bctsBlockECA(growth,inblock,assessYear,gdb):
    env.workspace = gdb
    env.overwriteOutput = True

    # Add ECA Field
    ecaField = 'ECA_Area'
    fieldType = 'DOUBLE'
    addField(inblock,ecaField,fieldType,gdb)

    # Calculate Data
    updateFields = ['HVS_STATUS_DATE','HVS_STATUS','Above_H60','SHAPE@AREA','ECA_Area']

    with arcpy.da.UpdateCursor(inblock,updateFields) as cursor:
        for row in cursor:
            if row[1] == 'P':
                startYear = assessYear  
            else:
                plantedYear = int(row[0].year) + 2
                if plantedYear > assessYear:
                    startYear = assessYear
                else:
                    startYear = plantedYear
                
            growthYears = assessYear - startYear
            growthAmount = growth * growthYears
                
            if growthAmount < 3.0:
                recovery = 0
            elif growthAmount >= 3.0 and growthAmount < 6.0:
                recovery = 25
            elif growthAmount >= 6.0 and growthAmount < 8.0:
                recovery = 50
            elif growthAmount >= 8.0 and growthAmount < 12.0:
                recovery = 75
            else:
                recovery = 100
                
            recoveryPercent = 1 - (recovery/100) #inverse of recovery 

            hectares = row[3] / 10000

            ecaHectares = recoveryPercent * hectares 
    #-------------------------------------------------------------------------------------------------------------------------------------------------
            if row[2] == 'Yes': #above the 60% elevation line.  This is where the issues is, h60 adjustment should not exceed total disturbed hectares  
                h60adjustment = (ecaHectares * 1.5)
                if h60adjustment >= hectares:
                    ecaHectares = hectares
                else:
                    ecaHectares = (ecaHectares * 1.5)
    #------------------------------------------------------------------------------------------------------------------------------------------------
            row[4] = ecaHectares

            cursor.updateRow(row)

def roadECA(inRoad,gdb):
    env.workspace = gdb
    env.overwriteOutput = True

    # Add ECA Field
    ecaField = 'ECA_Area'
    fieldType = 'DOUBLE'
    addField(inRoad,ecaField,fieldType,gdb)

    # Populate ECA field
    updateFields = ['SHAPE@AREA','ECA_Area','Above_H60']

    with arcpy.da.UpdateCursor(inRoad,updateFields) as cursor:
        for row in cursor:
            ecaArea = row[0] / 10000           
            row[1] = ecaArea

            cursor.updateRow(row)

def consolidatedBlockECA(inConBlock,growth,assessYear,gdb):
    env.workspace = gdb
    env.overwriteOutput = True

    # Add ECA Field
    ecaField = 'ECA_Area'
    fieldType = 'DOUBLE'
    addField(inConBlock,ecaField,fieldType,gdb)

    # Add eca data
    updateFields = ['HARVEST_YEAR','ECA_Area','Above_H60','SHAPE@AREA']

    with arcpy.da.UpdateCursor(inConBlock,updateFields) as cursor:
        for row in cursor:
            harvestYear = row[0] + 2

            if harvestYear > assessYear:
                startYear = assessYear
            else:
                startYear = harvestYear
            
            growthYears = assessYear - startYear
            growthAmount = growthYears * growth

            if growthAmount < 3.0:
                recovery = 0
            elif growthAmount >= 3.0 and growthAmount < 6.0:
                recovery = 25
            elif growthAmount >= 6.0 and growthAmount < 8.0:
                recovery = 50
            elif growthAmount >= 8.0 and growthAmount < 12.0:
                recovery = 75
            else:
                recovery = 100
                
            recoveryPercent = 1 - (recovery/100)

            hectares = row[3] / 10000

            ecaHectares = recoveryPercent * hectares

            if row[2] == 'Yes':
                h60adjustment = (ecaHectares * 1.5)
                if h60adjustment >= hectares:
                    ecaHectares = hectares
                else:
                    ecaHectares = (ecaHectares * 1.5)
                
            row[1] = ecaHectares

            cursor.updateRow(row)

def fireECA(inFireBlock,growth,assessYear,gdb):
    env.workspace = gdb
    env.overwriteOutput = True

    featureCount = int(arcpy.management.GetCount(inFireBlock).getOutput(0))
    
    if featureCount > 0:
    
        # Add ECA Field
        ecaField = 'ECA_Area'
        fieldType = 'DOUBLE'
        addField(inFireBlock,ecaField,fieldType,gdb)

        # Add ECA to Fire Data
        updateFields = ['FIRE_YEAR','ECA_Area','Above_H60','SHAPE@AREA']

        with arcpy.da.UpdateCursor(inFireBlock,updateFields) as cursor:
            for row in cursor:
                harvestYear = row[0] + 2

                if harvestYear > assessYear:
                    startYear = assessYear
                else:
                    startYear = harvestYear
            
                growthYears = assessYear - startYear
                growthAmount = growthYears * growth

                if growthAmount < 3.0:
                    recovery = 0
                elif growthAmount >= 3.0 and growthAmount < 6.0:
                    recovery = 25
                elif growthAmount >= 6.0 and growthAmount < 8.0:
                    recovery = 50
                elif growthAmount >= 8.0 and growthAmount < 12.0:
                    recovery = 75
                else:
                    recovery = 100
                
                recoveryPercent = 1 - (recovery/100)

                hectares = row[3] / 10000

                ecaHectares = recoveryPercent * hectares

                if row[2] == 'Yes':
                    h60adjustment = (ecaHectares * 1.5)
                    if h60adjustment >= hectares:
                        ecaHectares = hectares
                    else:
                        ecaHectares = (ecaHectares * 1.5)
                    
                row[1] = ecaHectares

                cursor.updateRow(row)

#---------------------------------------------------------------- Create Summary ----------------------------------------------------------------------------------------------------
def sumerizeData(watershed,inBlock,inRoad,inConBlock,inFireBlock,gdb,subBasin,subBasinName):
    env.workspace = gdb
    env.overwriteOutput = True

    watershedArea = 0
    with arcpy.da.SearchCursor(watershed,['SHAPE@AREA']) as cursor:
        for row in cursor:
            watershedArea += row[0]
    
    watershedAreaHa = watershedArea/10000

    blockArea = 0
    blockECA = 0
    with arcpy.da.SearchCursor(inBlock,['SHAPE@AREA','ECA_Area']) as cursor:
        for row in cursor:
            blockArea += row[0]
            blockECA += row[1]
    
    blockArea = blockArea/10000
    
    roadArea = 0
    roadECA = 0
    with arcpy.da.SearchCursor(inRoad,['SHAPE@AREA','ECA_Area']) as cursor:
        for row in cursor:
            roadArea += row[0]
            roadECA += row[1]
    
    roadArea = roadArea / 10000
    
    conBlockArea = 0
    conBlockECA = 0
    with arcpy.da.SearchCursor(inConBlock,['SHAPE@AREA','ECA_Area']) as cursor:
        for row in cursor:
            conBlockArea += row[0]
            conBlockECA += row[1]
    
    conBlockArea = conBlockArea/10000
    
    fireArea = 0
    fireECA = 0
    featureCount = int(arcpy.management.GetCount(inFireBlock).getOutput(0))
    if featureCount > 0:
        with arcpy.da.SearchCursor(inFireBlock,['SHAPE@AREA','ECA_Area']) as cursor:
            for row in cursor:
                fireArea += row[0]
                fireECA += row[1]
    
    fireArea = fireArea/10000
    
    totalDisturbanceArea = blockArea + roadArea + conBlockArea + fireArea
    totalECAarea = blockECA + roadECA + conBlockECA + fireECA
    ecaPercent = (totalECAarea / watershedAreaHa) * 100
    

    if subBasin == 'Yes':
        inFc = watershed
        field = [subBasinName]
        basinList = []

        with arcpy.da.SearchCursor(inFc,field) as cursor:
            for row in cursor:
                basinList.append(row[0])
        
        basinSet = set(basinList)
        basinList = list(basinSet)

        basinDict = dict.fromkeys(basinList)


        for key in basinDict:
            whereClause = subBasinName + '=' + "'"+ key + "'"

            watershedArea = 0
            with arcpy.da.SearchCursor(watershed,['SHAPE@AREA'],whereClause) as cursor:
                for row in cursor:
                    watershedArea += row[0]
    
            watershedAreaBasin = watershedArea/10000

            blockArea = 0
            blockECA = 0
            with arcpy.da.SearchCursor(inBlock,['SHAPE@AREA','ECA_Area'],whereClause) as cursor:
                for row in cursor:
                    blockArea += row[0]
                    blockECA += row[1]
    
            blockArea = blockArea/10000
    
            roadArea = 0
            roadECA = 0
            with arcpy.da.SearchCursor(inRoad,['SHAPE@AREA','ECA_Area'],whereClause) as cursor:
                for row in cursor:
                    roadArea += row[0]
                    roadECA += row[1]
    
            roadArea = roadArea / 10000
    
            conBlockArea = 0
            conBlockECA = 0
            with arcpy.da.SearchCursor(inConBlock,['SHAPE@AREA','ECA_Area'],whereClause) as cursor:
                for row in cursor:
                    conBlockArea += row[0]
                    conBlockECA += row[1]
    
            conBlockArea = conBlockArea/10000
    
            fireArea = 0
            fireECA = 0
            featureCount = int(arcpy.management.GetCount(inFireBlock).getOutput(0))
            if featureCount > 0:
                with arcpy.da.SearchCursor(inFireBlock,['SHAPE@AREA','ECA_Area'],whereClause) as cursor:
                    for row in cursor:
                        fireArea += row[0]
                        fireECA += row[1]
    
            fireArea = fireArea/10000
    
            totalDisturbanceAreaBasin = blockArea + roadArea + conBlockArea + fireArea
            totalECAreaBasin = blockECA + roadECA + conBlockECA + fireECA
            ecaPercentBasin = (totalECAreaBasin / watershedAreaBasin) * 100

            valueList = [watershedAreaBasin,totalDisturbanceAreaBasin,totalECAreaBasin,ecaPercentBasin]

            basinDict[key] = valueList
        
        

    nameString = 'Watershed Name'   
    watershedString = "Watershed Area"
    disturbanceString = "Disturbance Area"
    ecaString = "ECA Area"
    eacPerString = "ECA Percent"
    fullshed = 'Full Watershed'

    

    #Get folder gdb is in for script summary output
    parent = Path(gdb).parent

    csvName = 'ECA_Summary.csv'
    csvFile = os.path.join(parent,csvName)

    with open(csvFile,'w', newline='') as ecafile:
        csvReader = csv.writer(ecafile, delimiter=',')
        csvReader.writerow([nameString,watershedString,disturbanceString,ecaString,eacPerString])
        csvReader.writerow([fullshed,watershedAreaHa,totalDisturbanceArea,totalECAarea,ecaPercent])

        if subBasin == 'Yes':
            basinTitle = 'Sub Basin Name'
            basinAreaTitle = 'Sub Basin Area'
            basinDistTitle = 'Sub Basin Disturbance'
            basinECATitle = 'Sub Basin ECA'
            basinPercentTitle = 'Sub Basin ECA Percent'

            csvReader.writerow([basinTitle,basinAreaTitle,basinDistTitle,basinECATitle,basinPercentTitle])

            for key in sorted(basinDict.keys()):
                csvReader.writerow([key] + basinDict[key])

#----------------------------------------------------------------Create H60 Line -----------------------------------------------------------------------------------------------------
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

#------------------------------------------------------------------Execuites creation of the disturbance Layers and the Summary-------------------------------------------------------
def CalculateECA(growth,inBlock,inRoad,inConBlock,inFireBlock,watershed,assessYear,gdb,subBasin,subBasinName):
    print('Blocks')
    bctsBlockECA(growth,inBlock,assessYear,gdb)
    print('Roads')
    roadECA(inRoad,gdb)
    print('ConBlock')
    consolidatedBlockECA(inConBlock,growth,assessYear,gdb)
    print('Fire')
    fireECA(inFireBlock,growth,assessYear,gdb)
    print('Summary')
    sumerizeData(watershed,inBlock,inRoad,inConBlock,inFireBlock,gdb,subBasin,subBasinName)

#Creates Final Layers
def createDisturbanceLayer(GDB,FireBlocks,BCTSBlocks,ConBlocks,Roads):
    #This will create the disturbance layer for the ECA with all of the data in it

    #List of features to Add Fields to
    dataList = [FireBlocks,BCTSBlocks,ConBlocks,Roads]

    for fc in dataList:
        #Create a field for the Source
        addField(fc,'Origin','TEXT',GDB)

        #Populate our Source Field
        fields = ['Origin']

        #Get the Name of the Fc
        desc = arcpy.Describe(fc)
        fcName = desc.name

        with arcpy.da.UpdateCursor(fc,fields) as theCursor:
            for row in theCursor:
                if fcName == 'bctsBlocks_Id' or fcName == 'bctsBlocks_Id_Basin':
                    row[0] = 'BCTSblocks'
                elif fcName == 'bctsRoads_Id' or fcName == 'bctsRoads_Id_Basin':
                    row[0] = 'BCTSroads'
                elif fcName == 'ConsolidatedBlock_Id' or fcName == 'ConsolidatedBlock_Id_Basin':
                    row[0] = 'ConsolidatedBlocks'
                else:
                    row[0] = 'Fire'
                theCursor.updateRow(row)
                

    #merge the data together
    ECAlayer = 'ECA_DisturbanceLayer'
    merge(dataList,ECAlayer,GDB)

    #Cleanup the attribute table
    #Create list of fields we want to keep
    keepList = ['Origin','Above_H60','ECA_Area']

    removeFields = []
    
    fields = arcpy.ListFields(ECAlayer)
    arcpy.AddMessage('Cleaning out Attributes')
    for field in fields:
        if not field.required:
            removeFields.append(field.name)

    #Remove the keep list items
    deleteList = [x for x in removeFields if x not in keepList]

    arcpy.management.DeleteField(ECAlayer, deleteList)

#--------------------------------------------------------------Creates Base data, and runs the rest of the tools, such as H60 and the ECA Calculation
def createData(bcgwConnection,dbp06Connection,ingdb,watershed,indem,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock):
    #--------------------------DATA SETUP------------------------------------
    #Paths to temp workspaces
    Temp_BCGW = bcgwConnection
    Temp_DBP06 = dbp06Connection

    #----------------------Feature Classes for Processing --------------------------------------
    #Geodatabase
    gdb = ingdb
    
    #Watershed
    watershedFeature = watershed

    #Dem
    dem = indem
    
    #BCTS Blocks
    bctsBlockFeatureName = "FORESTVIEW.SV_BLOCK"
    bctsBlocks = os.path.join(Temp_DBP06, bctsBlockFeatureName)

    #BCTS Roads
    bctsRoadsFeatureName = r"FOREST.migration_dataset\FOREST.ROAD_SHAPE"
    bctsRoads = os.path.join(Temp_DBP06, bctsRoadsFeatureName)

    #BCTS SU
    bctsSUFeatureName = "FORESTVIEW.SV_SU"
    bctsSU = os.path.join(Temp_DBP06, bctsSUFeatureName)

    #FTEN Roads
    ftenRoadFeatureName = "WHSE_FOREST_TENURE.FTEN_ROAD_SECTION_LINES_SVW"
    ftenRoads = os.path.join(Temp_BCGW, ftenRoadFeatureName)

    #Consolidated Blocks
    ConsolidatedBlocksName = "WHSE_FOREST_VEGETATION.VEG_CONSOLIDATED_CUT_BLOCKS_SP"
    consolidatedBlocks = os.path.join(Temp_BCGW, ConsolidatedBlocksName)

    #Current Fires
    currentFiresBlockName = "WHSE_LAND_AND_NATURAL_RESOURCE.PROT_CURRENT_FIRE_POLYS_SP"
    currentFires = os.path.join(Temp_BCGW, currentFiresBlockName)

    #Historic Fires
    historicFiresBlocksName = "WHSE_LAND_AND_NATURAL_RESOURCE.PROT_HISTORICAL_FIRE_POLYS_SP"
    historicFires = os.path.join(Temp_BCGW, historicFiresBlocksName)

    # ----------------------- Clip features to Watershed --------------------------------------
    arcpy.AddMessage('Clipping Data')
    #Clip Bcts Blocks
    outBctsBlocks = "bctsBlocks_Clip"
    clip(bctsBlocks,watershedFeature,outBctsBlocks,gdb)

    #Clip Bcts Roads
    outBctsRoads = 'bctsRoads_Clip'
    clip(bctsRoads,watershedFeature,outBctsRoads,gdb)

    #Clip Bcts Su
    outBctsSU = 'bctsSU_Clip'
    clip(bctsSU,watershedFeature,outBctsSU,gdb)

    #Clip Ften Roads
    outftenRoad = 'ftenRoad_Clip'
    clip(ftenRoads,watershedFeature,outftenRoad,gdb)

    filterYear = assessYear - 25
    conWhere = '''DISTURBANCE_END_DATE >= timestamp ''' + "'" + str(filterYear) + '-01-01 12:00:00' + "'"
    selectCon = 'RecentConBlocks'

    makeFeatureLayer(consolidatedBlocks,selectCon,conWhere,gdb)
    # Clip consolidated blocks
    outConsolidatedBlock = 'consolidatedBlock_Clip'
    clip(consolidatedBlocks,watershedFeature,outConsolidatedBlock,gdb)

    #Clip current fires
    outCurrentFire = 'currentFire_Clip'
    clip(currentFires,watershedFeature,outCurrentFire,gdb)

    #Clip historic fires
    outHistoricFires = 'historicFire_Clip'
    clip(historicFires,watershedFeature,outHistoricFires,gdb)

    #------------------------ BCTS Blocks Remove WTRA/WTP/NP Su --------------------------
    arcpy.AddMessage('Creating Block Data')
    if PlannedBlock == 'No':
        whereBlock = '''CUTB_BLOCK_STATE IN ('ADV','LC','HB')''' #+ ''' AND  + '''HVS_STATUS_DATE >= timestamp '''+ "'" + str(filterYear) + '-01-01 12:00:00' + "'"
    else:
        whereBlock = '''CUTB_BLOCK_STATE IN ('ADV','LC','HB','PP','WIP')'''
    
    selectBlock = 'BctsBlockSelection'

    makeFeatureLayer(outBctsBlocks,selectBlock,whereBlock,gdb)
    
    whereSu = "STUN_ID IN ('WTRA','WTP','NP','INTRES','OTHER')"
    selectSu = 'SuSelection'

    makeFeatureLayer(outBctsSU,selectSu,whereSu,gdb)

    erasedBlocks = 'bctsBlocks_Erased'
    erase(selectBlock,selectSu,erasedBlocks,gdb)

    #------------------------ Create Roads Right of Way---------------------------------
    arcpy.AddMessage('Creating Roads Data')
    mergeRoads = 'mergedRoads'
    mergeList = [outBctsRoads,outftenRoad]

    merge(mergeList,mergeRoads,gdb)

    bufferedRoads = 'roads_Buffer10m'
    buffer(mergeRoads,bufferedRoads,gdb)

    clippedBufferRds = 'roads_Buffer10m_Clip' 
    clip(bufferedRoads,watershedFeature,clippedBufferRds,gdb)
    
    #------------------------ Fire Data -----------------------------------------------
    arcpy.AddMessage('Creating Fire Data')
    filterYear = assessYear - 25
    historicWhere = "FIRE_YEAR >= " + str(filterYear)
    selectHistoric = 'HistoricFires_2000onward'

    makeFeatureLayer(outHistoricFires,selectHistoric,historicWhere,gdb)

    mergeFires = 'firesMerged'
    firesToMerge = [selectHistoric,outCurrentFire]
    merge(firesToMerge,mergeFires,gdb)


    #----------------------------Create H60 Data ---------------------------------------
    arcpy.AddMessage('Creating H60 Data')
    createH60(dem,gdb)

    #---------------------- Remove Roads from the Block Data ---------------------------
    bctsBlockErase = 'bctsBlocks_roadsErased'
    erase(erasedBlocks,clippedBufferRds,bctsBlockErase,gdb)
    conBlockErased = 'consolidatedBlock_Erased'
    erase(outConsolidatedBlock,clippedBufferRds,conBlockErased,gdb)
    fireBlockErase = 'firesMerged_Erased'
    erase(mergeFires,clippedBufferRds,fireBlockErase,gdb)

    #--------------------Remove BCTS blocks from consolidated blocks to account of overlap ------------
    ConBlocksNoBCTS = 'consolidatedBlock_Erased_BCTS'
    erase(conBlockErased,bctsBlockErase,ConBlocksNoBCTS,gdb)

    #--------------------- Identity H60 onto Block, Road and Fire Data -----------------
    arcpy.AddMessage('Adding H60 Data to Disturbance Data')
    inBctsBlock = 'bctsBlocks_roadsErased'
    outBlock = 'bctsBlocks_Id'
    inBctsRoads = 'roads_Buffer10m_Clip'
    outRoad = 'bctsRoads_Id'
    inConBlock = 'consolidatedBlock_Erased_BCTS'
    outConBlock = 'ConsolidatedBlock_Id'
    inFireData = 'firesMerged_Erased'
    outFire = 'firesMerged_Id'
    indentityFc = 'Upper_H60'

    identity(inBctsBlock,indentityFc,outBlock,gdb)
    identity(inBctsRoads,indentityFc,outRoad,gdb)
    identity(inConBlock,indentityFc,outConBlock,gdb)
    identity(inFireData,indentityFc,outFire,gdb)

    #--------------------- Add Above/Below H60 identifier -----------------------------
    arcpy.AddMessage('Adding Above or Below H60')
    featureList = [outBlock,outRoad,outConBlock,outFire]
    inField = 'Above_H60'
    fieldType = 'TEXT'

    for fc in featureList:
        addField(fc,inField,fieldType,gdb)
    

    H60Field = 'FID_Upper_H60'
    fieldList = [inField,H60Field]
    
    for feature in featureList:
        with arcpy.da.UpdateCursor(feature,fieldList) as cursor:
            for row in cursor:
                if row[1] >= 0:
                    row[0] = 'Yes'
                else:
                    row[0] = 'No'
                cursor.updateRow(row)

    #---------------------------------------Sub Basins ----------------------------------
    if subBasin == 'Yes':
        arcpy.AddMessage('Adding in SubBasin Data')
        identity(outBlock,watershedFeature,'bctsBlocks_Id_Basin',gdb)
        identity(outRoad,watershedFeature,'bctsRoads_Id_Basin',gdb)
        identity(outConBlock,watershedFeature,'ConsolidatedBlock_Id_Basin',gdb)
        identity(outFire,watershedFeature,'firesMerged_Id_Basin',gdb)

    #---------------------------------- Create ECA Spreadsheet ---------------------------
    arcpy.AddMessage('Calculating ECA Data')
    if subBasin == 'Yes':
        inBlock = 'bctsBlocks_Id_Basin'
        inRoad = 'bctsRoads_Id_Basin'
        inConBlock = 'ConsolidatedBlock_Id_Basin'
        inFire = 'firesMerged_Id_Basin'
    else:
        inBlock = 'bctsBlocks_Id'
        inRoad = 'bctsRoads_Id'
        inConBlock = 'ConsolidatedBlock_Id'
        inFire = 'firesMerged_Id'

    CalculateECA(growthFactor,inBlock,inRoad,inConBlock,inFire,watershedFeature,\
        assessYear,gdb,subBasin,subBasinName)
    

    createDisturbanceLayer(ingdb,inFire,inBlock,inConBlock,inRoad)


def main():
    bcgwConnection = arcpy.GetParameterAsText(0)
    dbp06Connection = arcpy.GetParameterAsText(1)
    geodatabase = arcpy.GetParameterAsText(2)
    watershed = arcpy.GetParameterAsText(3)
    DEM = arcpy.GetParameterAsText(4)
    assessYear = int(arcpy.GetParameterAsText(5))
    growthFactor = float(arcpy.GetParameterAsText(6))
    subBasin = arcpy.GetParameterAsText(7)
    subBasinName = arcpy.GetParameterAsText(8)
    PlannedBlock = arcpy.GetParameterAsText(9)

    createData(bcgwConnection,dbp06Connection,geodatabase,watershed,DEM,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock)
    arcpy.AddMessage('Removing Un-needed Data')
    delete(geodatabase)
    arcpy.AddMessage('Finished')
    
main()