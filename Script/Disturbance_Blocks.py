import arcpy, string, pathlib, os, sys
from arcpy import env
import H60_Creation
import ECA_Calculations

PYTHON_SCRIPT   = sys.argv[0]

# This function connects to the BCGW workspace
def BCGW(username,password,path):
    arcpy.AddMessage('running BCGW connection')
    name = 'Temp_BCGW'
    database_platform = 'ORACLE'
    account_authorization  = 'DATABASE_AUTH'
    instance = 'bcgw.bcgov/idwprod1.bcgov'

    if arcpy.Exists(os.path.join(path,'Temp_BCGW.sde')):
        try:
            arcpy.Delete_management(os.path.join(path,'Temp_BCGW.sde'))
        except:
            pass

    arcpy.CreateDatabaseConnection_management (path,name,database_platform,\
    instance,account_authorization,username ,password,'DO_NOT_SAVE_USERNAME')

# This function conects to the DBP06 workspace
def DBP06(username,password,path):
    arcpy.AddMessage('running DBP06 connection')
    name = 'Temp_DBP06'
    database_platform = 'ORACLE'
    account_authorization  = 'DATABASE_AUTH'
    instance = 'lrmbctsp.nrs.bcgov/dbp06.nrs.bcgov'

    if arcpy.Exists(os.path.join(path,'Temp_DBP06.sde')):
        try:
            arcpy.Delete_management(os.path.join(path,'Temp_DBP06.sde'))
        except:
            pass

    arcpy.CreateDatabaseConnection_management (path,name,database_platform,\
    instance,account_authorization,username ,password,'DO_NOT_SAVE_USERNAME')

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

def createData(bcgwUser,bcgwPass,dbp06User,dbp06Pass,ingdb,watershed,indem,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock):
    # --------------------------DATA SETUP------------------------------------
    # Get the folder path for the script
    drive_path = os.path.split(PYTHON_SCRIPT)[0] # F:\......
    drive_tail = os.path.splitdrive(drive_path) # F:[0] \....[1]
    newPath = pathlib.Path(drive_tail[0]).resolve() # Changes F: to \\bctsdata.bcgov\.....
    script_path = os.path.join(newPath, drive_tail[1]) # Creates Full UNC path to script

    arcpy.AddMessage(script_path)
    # Get login Info for the databases
    bcgw_user_name = bcgwUser
    bcgw_password = bcgwPass
    DBP06_username = dbp06User
    DBP06_password = dbp06Pass

    arcpy.AddMessage('Connecting to Databases')

    #Calling functions to connect to workspaces
    BCGW(bcgw_user_name,bcgw_password,script_path)
    DBP06(DBP06_username,DBP06_password,script_path)

    #Paths to temp workspaces
    Temp_BCGW = script_path + r'\Temp_BCGW.sde'
    Temp_DBP06 = script_path + r'\Temp_DBP06.sde'

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
    
    whereSu = "STUN_ID IN ('WTRA','WTP','NP')"
    selectSu = 'SuSelection'

    makeFeatureLayer(outBctsSU,selectSu,whereSu,gdb)

    erasedBlocks = 'bctsBlocks_Erased'
    erase(selectBlock,selectSu,erasedBlocks,gdb)

    #------------------------ Create Roads ROW -------------------------------------------
    arcpy.AddMessage('Creating Roads Data')
    mergeRoads = 'mergedRoads'
    mergeList = [outBctsRoads,outftenRoad]

    merge(mergeList,mergeRoads,gdb)

    bufferedRoads = 'roads_Buffer10m'
    buffer(mergeRoads,bufferedRoads,gdb)

    clippedBuffer = 'roads_Buffer10m_Clip' 
    clip(bufferedRoads,watershedFeature,clippedBuffer,gdb)
    
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
    H60_Creation.createH60(dem,gdb)

    #---------------------- Remove Roads from the Block Data ---------------------------
    bctsBlockErase = 'bctsBlocks_roadsErased'
    erase(erasedBlocks,clippedBuffer,bctsBlockErase,gdb)
    conBlockErased = 'consolidatedBlock_Erased'
    erase(outConsolidatedBlock,clippedBuffer,conBlockErased,gdb)
    fireBlockErase = 'firesMerged_Erased'
    erase(mergeFires,clippedBuffer,fireBlockErase,gdb)

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

    ECA_Calculations.CalculateECA(growthFactor,inBlock,inRoad,inConBlock,inFire,watershedFeature,\
        assessYear,gdb,subBasin,subBasinName,script_path)

    # Remove Temp GDB
    os.remove(Temp_BCGW)
    os.remove(Temp_DBP06)

def delete(gdb):
    env.workspace = gdb
    featureList = ['bctsBlocks_Clip','bctsRoads_Clip','bctsSU_Clip','ftenRoad_Clip','consolidatedBlock_Clip',\
        'currentFire_Clip','historicFire_Clip','bctsBlocks_Erased','mergedRoads','roads_Buffer10m',\
            'roads_Buffer10m_Clip','HistoricFires_2000onward','firesMerged','DEM_Slice100','Slice100_Polygon',\
                'Slice100_Polygon_H60_Erased','Slice100_Polygon_Sorted','Upper_H60_MultiPolygons',\
                    'bctsBlocks_roadsErased','consolidatedBlock_Erased','firesMerged_Erased']
    
    for feature in featureList:
        arcpy.management.Delete(feature)

def main():
    bcgwUsername = arcpy.GetParameterAsText(0)
    bcgwPassword = arcpy.GetParameterAsText(1)
    dbp06Username = arcpy.GetParameterAsText(2)
    dbp06Password = arcpy.GetParameterAsText(3)
    geodatabase = arcpy.GetParameterAsText(4)
    watershed = arcpy.GetParameterAsText(5)
    DEM = arcpy.GetParameterAsText(6)
    assessYear = int(arcpy.GetParameterAsText(7))
    growthFactor = float(arcpy.GetParameterAsText(8))
    subBasin = arcpy.GetParameterAsText(9)
    subBasinName = arcpy.GetParameterAsText(10)
    PlannedBlock = arcpy.GetParameterAsText(11)

    createData(bcgwUsername,bcgwPassword,dbp06Username,dbp06Password,geodatabase,watershed,DEM,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock)
    arcpy.AddMessage('Removing Un-needed Data')
    delete(geodatabase)
    arcpy.AddMessage('Finished')
    
main()
