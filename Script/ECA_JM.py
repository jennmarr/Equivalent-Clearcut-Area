# Spreadsheet Driven Version
# Date             : Jul 16 2025
#
# Author:          : Jennifer Marr (jennifer.marr@gov.bc.ca)
#
# Purpose:         : Find ECA for a given watershed
#
# Inputs:          : database connections, working and output GDB, watershed polygons, DEM of watershed, year of assessment, growth factor, use sub-basins (yes or no), if yes sub-basin field name, use planned blocks (yes/no)
#
# History:         : (2025-07-16) Finished first draft of script
#                  : (2025-09-09) add YearofDisturbance field to MergedECA feature class, only export final feature classes of factors that have are not empty, set name of excel output to match GDB name, so can batch run
#                  : (2025-09-10) add capacity to add own planned blocks feature class if not in LRM yes
#                  : (2025-11-27) account for overlapping disturbance areas to prevent ECA over 100%
#                  : (2025-12-03) switch to run off memory
#=========================================================================================================

# change test

import arcpy, pathlib, os, sys,csv,math
from pathlib import Path
from arcpy import env
from arcpy.sa import *

#-------------------------------------------------------------------------Base Functions -------------------------------------------------------------------------------------------
def delete():
    keep_list = ["H60_Line", "Lower_H40", "Upper_H60", "MergedECA","DisturbanceLayer_Adjusted"]

    # List all feature classes
    feature_classes = arcpy.ListFeatureClasses()

    for fc in feature_classes:
        if fc.endswith("Final"):
            count = int(arcpy.management.GetCount(fc)[0])
            if count == 0: 
                pass
            else: 
                keep_list.append(fc)

    # print(keep_list)
    # print(feature_classes)

    for fc in feature_classes:
        if fc in keep_list: 
            pass
        else:
            arcpy.Delete_management(fc)

#---------------------------------------------------------------- Write to Excel ----------------------------------------------------------------------------------------------------

def writetoExcel(watershed, inECAMerged, subBasin, subBasinName, outputExcelName):

    full_path = arcpy.Describe(inECAMerged).catalogPath

    # Calculate watershed area
    watershedArea = 0
    with arcpy.da.SearchCursor(watershed, ['SHAPE@AREA']) as cursor:
        for row in cursor:
            watershedArea += row[0]
    
    watershedAreaHa = watershedArea / 10000

    # # Sub-basin processing
    basinDict = {}
    if subBasin == 'Yes':
        field = [subBasinName]
        basinSet = set()
        with arcpy.da.SearchCursor(watershed, field) as cursor:
            for row in cursor:
                basinSet.add(row[0])
        basinList = list(basinSet)

        for key in basinList:
            whereClause = f"{subBasinName} = '{key}'"

            watershedArea = 0
            with arcpy.da.SearchCursor(watershed, ['SHAPE@AREA'], whereClause) as cursor:
                for row in cursor:
                    watershedArea += row[0]
    
            watershedAreaBasin = watershedArea / 10000

            # Get disturbance area from global dictionary
            disturbanceArea = disturbance_area_final.get(key, 0)
            
            totalECA = 0
            with arcpy.da.SearchCursor(inECAMerged, ['SUM_ECA_Area_ADJ'], whereClause) as cursor:
                for row in cursor:
                    totalECA += row[0]

            ecaPercentBasin = (totalECA / watershedAreaBasin) * 100

            valueList = [watershedAreaBasin, disturbanceArea, totalECA, ecaPercentBasin]
            basinDict[key] = valueList

    # Calculate total ECA for watershed from merged input
    totalECA = 0
    with arcpy.da.SearchCursor(inECAMerged, ['SUM_ECA_Area_ADJ']) as cursor:
        for row in cursor:
            totalECA += row[0]
    
    # Get total disturbance area - sum dictionary values if subBasin, otherwise use value directly
    if subBasin == 'Yes' and isinstance(disturbance_area_final, dict):
        disturbanceArea = sum(disturbance_area_final.values())
    else:
        disturbanceArea = disturbance_area_final

    ecaPercent = (totalECA / watershedAreaHa) * 100


    # CSV output
    nameString = 'Watershed Name'   
    watershedString = "Watershed Area"
    disturbanceString = "Disturbance Area"
    ecaString = "ECA Area"
    eacPerString = "ECA Percent"
    fullshed = 'Full Watershed'

    parent = Path(geodatabase).parent
    csvName = outputExcelName + '_ECA.csv'
    csvFile = os.path.join(parent, csvName)

    with open(csvFile, 'w', newline='') as ecafile:
        csvWriter = csv.writer(ecafile, delimiter=',')
        csvWriter.writerow([nameString, watershedString, disturbanceString, ecaString, eacPerString])
        csvWriter.writerow([fullshed, watershedAreaHa, disturbanceArea, totalECA, ecaPercent])

        if subBasin == 'Yes':
            csvWriter.writerow(['Sub Basin Name', 'Sub Basin Area', 'Sub Basin Disturbance', 'Sub Basin ECA', 'Sub Basin ECA Percent'])
            for key in sorted(basinDict.keys()):
                csvWriter.writerow([key] + basinDict[key])



    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font
    from openpyxl.utils import get_column_letter

    # Create workbook and sheet
    wb = Workbook()
    ws = wb.active
    ws.title = "ECA Summary"

    # Define header styles
    header_fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")
    header_font = Font(bold=True)

    # Collect all rows to write (as lists of values)
    rows = []

    # Main watershed summary headers and data
    headers = ['Watershed Name', 'Watershed Area', 'Disturbance Area', 'ECA Area', 'ECA Percent']
    rows.append(headers)
    rows.append(['Full Watershed', watershedAreaHa, disturbanceArea, totalECA, ecaPercent])

    # Optional sub-basin data
    if subBasin == 'Yes':
        rows.append([])  # blank line
        sub_headers = ['Sub Basin Name', 'Sub Basin Area', 'Sub Basin Disturbance', 'Sub Basin ECA', 'Sub Basin ECA Percent']
        rows.append(sub_headers)

        for key in sorted(basinDict.keys()):
            rows.append([key] + basinDict[key])

    # Write rows to sheet
    for row_index, row_data in enumerate(rows, start=1):
        for col_index, value in enumerate(row_data, start=1):
            if isinstance(value, (int, float)):
                value = round(value, 2)
            cell = ws.cell(row=row_index, column=col_index, value=value)

            # Style header rows
            if row_index in [1, 4]:  # First and sub-basin header row
                cell.fill = header_fill
                cell.font = header_font

    # Auto-fit columns based on max length in each column
    for col in ws.columns:
        max_length = 0
        column = col[0].column  # Get column index (A, B, C...)
        column_letter = get_column_letter(column)
        for cell in col:
            try:
                if cell.value is not None:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        adjusted_width = max_length + 2
        ws.column_dimensions[column_letter].width = adjusted_width

    # Save workbook
    xlsxName = outputExcelName + '_ECA.xlsx'
    xlsxFile = os.path.join(parent, xlsxName)
    wb.save(xlsxFile)

    # Delete old CSV if it exists
    csvFile = os.path.join(parent, outputExcelName + '_ECA.csv')
    if os.path.exists(csvFile):
        os.remove(csvFile)





#----------------------------------------------------------------Create H60 Line -----------------------------------------------------------------------------------------------------
def createH60(dem, geodatabase):

    env.overwriteOutput = True

    #Assign watershed DEM to the Input data
    watershedDEM = dem

    # -------------------------------------------------------------------------------
    # Slice DEM into 100 equal area pieces
    if arcpy.CheckExtension('Spatial') == 'Available':
        arcpy.CheckOutExtension('Spatial')
        numberZones = 100
        outSlice = arcpy.sa.Slice(watershedDEM, numberZones, "EQUAL_AREA") #if failing here do this step in ArcMap
        outSlice.save("in_memory/DEM_Slice100")
    # -------------------------------------------------------------------------------

    # Turn Slice raster into polygon feature class
    arcpy.AddMessage('Convert Slice into polygon')
    inRaster = 'in_memory/DEM_Slice100'
    outPoly = 'Slice100_Polygon'

    arcpy.RasterToPolygon_conversion(inRaster, outPoly,"NO_SIMPLIFY","VALUE")

    # Use search cursor to get the total area of the slice
    fields = ['SHAPE@AREA']
    inFc = outPoly
    totalArea = 0

    with arcpy.da.SearchCursor(inFc, fields) as cursor:
        for row in cursor:
            totalArea += row[0]

    # Add field 'percent'
    fieldName = 'Percent' 
    arcpy.AddField_management(inFc, fieldName, "DOUBLE")

    # Calculate percent of each slice
    expression = "!shape.area!/ {} * 100".format(totalArea)    
    arcpy.CalculateField_management (inFc, fieldName, expression, 'PYTHON_9.3')

    # Sort by grid code decending, this makes it so the layers are properly ordered so we can attain the upper 60 using a cursor in the right order.
    outFeature = 'Slice100_Polygon_Sorted'
    sortField = [['gridcode','Descending']]

    arcpy.Sort_management(inFc, outFeature, sortField)

    # Use the sorted feature to start a running total to 60%, populating a list with the gridcodes
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
    expression = 'gridcode IN {0}'.format(tuple(codeList))
    fc60 = 'Upper60_Temp'
    fcOut = 'Upper_H60_MultiPolygons'

    arcpy.MakeFeatureLayer_management(loopFeature,fc60,expression)

    # Export the in memory selection to a feature class
    arcpy.management.CopyFeatures(fc60, fcOut)        

    # Dissolve the polygons in the new feature class, this will then represent the upper 60% of the watershed
    finalFc = os.path.join(geodatabase, 'Upper_H60')
    arcpy.Dissolve_management (fcOut, finalFc)

    # Erase upper 60 from the slice to create the lower 40%
    FullSlice = 'Slice100_Polygon'
    Slice40 = 'Slice100_Polygon_H60_Erased'

    arcpy.analysis.PairwiseErase(FullSlice,finalFc, Slice40)

    # Dissolve the lower 40% into one polygon
    inDissolve = Slice40
    outDissolve = os.path.join(geodatabase, "Lower_H40")

    arcpy.Dissolve_management (inDissolve, outDissolve)

    # Turn the lower 40% into a line feature. The reason to do this is bacause the upper 60% will have a line
    # on the outside and inside of the watershed, where the lower 40 will not and the exterior edge represents the same thing.
    inPoly = outDissolve
    outLine = os.path.join(geodatabase, 'H60_Line')

    arcpy.PolygonToLine_management (inPoly,outLine)




#--------------------------------------------------------------Creates Base data, and runs the rest of the tools, such as H60 and the ECA Calculation
def createData(bcgwConnection,dbp06Connection,watershed,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock,PlannedBlockFeatureClass):
    global geodatabase
    
    #--------------------------DATA SETUP------------------------------------
    #Paths to temp workspaces
    Temp_BCGW = bcgwConnection
    Temp_DBP06 = dbp06Connection
    watershedFeature = watershed
                                                                                       

    filterYear = assessYear - 25 #remove old features that are beyond ECA affect, to speed up processing

    #dictionary structure  - name: [source, query (if there is one)]    
    featurefromBCGW = {
        'transmissionTantalis': ['WHSE_TANTALIS.TA_CROWN_TENURES_SVW', "NOT(TENURE_STAGE = 'APPLICATION' AND APPLICATION_TYPE_CDE = 'NEW') AND TENURE_SUBTYPE NOT IN('INVESTIGATIVE LICENCE') AND TENURE_SUBPURPOSE IN ('TRANSMISSION LINE', 'ELECTRIC POWER LINE')"],
        'bctsBlocks': ['FORESTVIEW.SV_BLOCK'],
        'bctsSU': ['FORESTVIEW.SV_SU', "STUN_ID IN ('WTRA','WTP','NP','INTRES','OTHER')"],
        'bctsRoads': ["FOREST.migration_dataset\FOREST.ROAD_SHAPE"],
        'ftenRoads': ["WHSE_FOREST_TENURE.FTEN_ROAD_SECTION_LINES_SVW"],
        'consolidatedBlocks': ["WHSE_FOREST_VEGETATION.VEG_CONSOLIDATED_CUT_BLOCKS_SP"],
        'firesHist': ["WHSE_LAND_AND_NATURAL_RESOURCE.PROT_HISTORICAL_FIRE_POLYS_SP","FIRE_YEAR >= " + str(filterYear)],
        'firesCurrent': ["WHSE_LAND_AND_NATURAL_RESOURCE.PROT_CURRENT_FIRE_POLYS_SP"],
        'privateLand': ["WHSE_CADASTRE.PMBC_PARCEL_FABRIC_POLY_FA_SVW", "OWNER_TYPE = 'Private'"],
        'pestHist': ["WHSE_FOREST_VEGETATION.PEST_INFEST_HISTORIC_POLY", "CAPTURE_YEAR >= " + str(filterYear)],
        'pestCurrent': ["WHSE_FOREST_VEGETATION.PEST_INFEST_CURRENT_POLY"],
        'railways' : ["WHSE_BASEMAPPING.GBA_RAILWAY_TRACKS_SP", "TRACK_CLASSIFICATION IN ('Connecting', 'Main')"],
        'vri': ["WHSE_FOREST_VEGETATION.VEG_COMP_LYR_R1_POLY"],
        'burnSeverityCurrent': ['WHSE_FOREST_VEGETATION.VEG_BURN_SEVERITY_SAME_YR_SP'],
        'burnSeverityHist': ['WHSE_FOREST_VEGETATION.VEG_BURN_SEVERITY_SP'],
        'pipelineGDM': ['WHSE_IMAGERY_AND_BASE_MAPS.DRP_OIL_GAS_PIPELINES_BC_SP', "OPERATIONAL_STATUS IN ( 'ACTIVE', 'APPROVED', 'OPERATING')"],
        'pipelineFortisBC': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Oil_and_Gas\FortisBC_Gas.gdb\TRANSMISSION_PIPE', "STATUS NOT IN ('Removed', 'Proposed')"],
        'pipelinePacificNG': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Oil_and_Gas\PacificNorthernGas.gdb\GAS_LINE'], 
        'pipelineEnbridge': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Oil_and_Gas\Enbridge.gdb\PIPELINE'], 
        'pipelineKinderMorgan': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Oil_and_Gas\KinderMorgan.gdb\PIPELINE_CENTERLINE'], 
        'pipelineRightofWay': ['WHSE_MINERAL_TENURE.OG_PIPELINE_AREA_PERMIT_SP', "CONSTRUCTION_DESC = 'Constructed' AND LAND_STAGE_EFF_DATE > timestamp '2010-12-12 11:22:07'"], 
        'pipelineTantalis': ['WHSE_TANTALIS.TA_CROWN_TENURES_SVW', "APPLICATION_TYPE_CDE <> 'NEW' AND TENURE_SUBTYPE <> 'INVESTIGATIVE LICENCE' AND TENURE_STAGE = 'TENURE' AND TENURE_SUBPURPOSE = 'GAS AND OIL PIPELINE' AND CROWN_LANDS_FILE <>'0343439' OR INTRID_SID IN (260032, 265936, 899535, 878882)"], 
        'transmissionGBA': ['WHSE_BASEMAPPING.GBA_TRANSMISSION_LINES_SP'],
        'transmissionBCHydroOverhead': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Hydro\BCHydro.gdb\OH_PRIMARY'], 
        'transmissionBCHydroUnderground': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Hydro\BCHydro.gdb\UG_PRIMARY'], 
        'transmissionFortisBC': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Hydro\FortisBC_Electric.gdb\TRANSMISSION_OH_LINES'], 
        'transmissionFortisBCDistribution': [r'\\Spatialfiles.bcgov\work\ilmb\PEP\data_restricted\Critical_Infrastructure\Hydro\FortisBC_Electric.gdb\DIST_PRIMARY_OH_CONDUCTOR'], 
        'transmissionConduitsNTS': ['WHSE_BASEMAPPING.NTS_BC_WATER_LINES_125M', "FCODE IN ('EA06100000', 'EA06100130')"]
    }
    

    arcpy.AddMessage('Clipping Data')
    for key in featurefromBCGW:

        source = featurefromBCGW[key][0] #"WHSE_CADASTRE.PMBC_PARCEL_FABRIC_POLY_FA_SVW"
        if source.startswith("\\\\"): #local
            sourcePath = source

        elif source.startswith("FOREST"): #DBP06
            sourcePath = os.path.join(Temp_DBP06, source) 

        else: #BCGW
            sourcePath = os.path.join(Temp_BCGW, source) 

        clipName = key + "_Clip" #e.g. privateLand_Clip

        if len(featurefromBCGW[key]) > 1: #query present
            clipNameBQ = clipName + "Unqueried"
            arcpy.analysis.PairwiseClip(sourcePath,watershedFeature,clipNameBQ)

            query = str(featurefromBCGW[key][1]) #e.g. "OWNER_TYPE = 'Private'"
            arcpy.conversion.ExportFeatures(clipNameBQ, clipName, query)                                       

        else:
            arcpy.analysis.PairwiseClip(sourcePath,watershedFeature,clipName)

    # # dissolve VRI 
    arcpy.AddMessage('Dissolving VRI')
    vri_siteIndex = 'VRI_Dissolved'
    arcpy.management.Dissolve('vri_Clip', vri_siteIndex, ['SITE_INDEX'])

    #------------------------Buffer Transmission Lines--------------------------
    arcpy.AddMessage('Creating Transmission Line Data')
    mergedTransmissionLines = 'mergedTransmissionLines'
    mergeList = ['transmissionGBA_Clip','transmissionBCHydroOverhead_Clip','transmissionBCHydroUnderground_Clip','transmissionFortisBC_Clip','transmissionFortisBCDistribution_Clip','transmissionConduitsNTS_Clip']

    arcpy.management.Merge(mergeList,mergedTransmissionLines)

    bufferedTL = 'transmission_Buffer30m'
    arcpy.analysis.PairwiseBuffer(mergedTransmissionLines, bufferedTL, '15 Meters','ALL')

    clippedBufferTransmission = 'roads_Transmission30m_Clip' 
    arcpy.analysis.PairwiseClip(bufferedTL,watershedFeature,clippedBufferTransmission)
    
    #------------------------Merge Pipelines Data--------------------------
    arcpy.AddMessage('Creating Pipeline Data')
    mergePipelines = 'mergedPipelines'
    mergeList = ['pipelineGDM_Clip','pipelineFortisBC_Clip','pipelineEnbridge_Clip','pipelineKinderMorgan_Clip'] 

    arcpy.management.Merge(mergeList,mergePipelines) 

    bufferedPipelines = 'roads_Pipelines10m'
    arcpy.analysis.PairwiseBuffer(mergePipelines,bufferedPipelines, '5 Meters','ALL')

    #add pipeline polygon features
    bufferedPipelinesPoly = 'roads_PipelinesPoly10m'
    arcpy.management.Merge(['pipelineRightofWay_Clip','pipelineTantalis_Clip',bufferedPipelines],bufferedPipelinesPoly)

    clippedBufferPipelines = 'roads_Pipelines10m_Clip' 
    arcpy.analysis.PairwiseClip(bufferedPipelinesPoly,watershedFeature,clippedBufferPipelines)

    #------------------------Merge and Buffer Roads--------------------------
    arcpy.AddMessage('Creating Roads Data')
    mergeRoads = 'mergedRoads'
    mergeList = ['bctsRoads_Clip','ftenRoads_Clip']

    arcpy.management.Merge(mergeList,mergeRoads)

    bufferedRoads = 'roads_Buffer10m'
    arcpy.analysis.PairwiseBuffer(mergeRoads,bufferedRoads, '5 Meters','ALL')

    clippedBufferRoads = 'roads_Buffer10m_Clip' 
    arcpy.analysis.PairwiseClip(bufferedRoads,watershedFeature,clippedBufferRoads)
    

    #------------------------Buffer Railways Lines--------------------------
    bufferedRW = 'railways_Buffer6m'
    arcpy.analysis.PairwiseBuffer('railways_Clip',bufferedRW, '3 Meters','ALL')


    #------------------------Erase overlapping non-recovering features--------------------------NEW
    arcpy.AddMessage('Removing overlaps from non-recovering features')
    # Erase roads from pipelines
    clippedBufferPipelines_Erased = 'roads_Pipelines10m_Clip_Erased'
    arcpy.analysis.PairwiseErase(clippedBufferPipelines, clippedBufferRoads, clippedBufferPipelines_Erased)
    
    # Erase roads and pipelines from transmission
    clippedBufferTransmission_Erased = 'roads_Transmission30m_Clip_Erased'
    arcpy.management.Merge([clippedBufferRoads, clippedBufferPipelines_Erased], 'roads_pipelines_merged')
    arcpy.analysis.PairwiseErase(clippedBufferTransmission, 'roads_pipelines_merged', clippedBufferTransmission_Erased)
    
    # Erase roads, pipelines, and transmission from railways
    bufferedRW_Erased = 'railways_Buffer6m_Erased'
    arcpy.management.Merge([clippedBufferRoads, clippedBufferPipelines_Erased, clippedBufferTransmission_Erased], 'roads_pipelines_transmission_merged')
    arcpy.analysis.PairwiseErase(bufferedRW, 'roads_pipelines_transmission_merged', bufferedRW_Erased)
    
    # Erase roads, pipelines, transmission, and railways from private land
    privateLand_Erased = 'privateLand_Clip_Erased'
    arcpy.management.Merge([clippedBufferRoads, clippedBufferPipelines_Erased, clippedBufferTransmission_Erased, bufferedRW_Erased], 'all_infrastructure_merged')
    arcpy.analysis.PairwiseErase('privateLand_Clip', 'all_infrastructure_merged', privateLand_Erased)


    #------------------------Merge Pest Layer--------------------------
    arcpy.AddMessage('Merging Pest Data')    
    mergePests = 'mergedPests'
    mergeList = ['pestHist_Clip','pestCurrent_Clip']
    arcpy.management.Merge(mergeList,mergePests)


    #------------------------Merge Burn Severity Layer--------------------------
    arcpy.AddMessage('Merging Burn Severity')
    mergeBurnSeverity = 'mergedBurnSeverity'
    mergeList = ['burnSeverityCurrent_Clip','burnSeverityHist_Clip']
    arcpy.management.Merge(mergeList,mergeBurnSeverity)


    #------------------------ Merge Fire Data ----------------------------------------------- 
    arcpy.AddMessage('Merging Fire Data')
    mergeFires = 'firesMerged'
    mergeList = ['firesCurrent_Clip','firesHist_Clip']
    arcpy.management.Merge(mergeList,mergeFires)


    #------------------------ BCTS Blocks Remove WTRA/WTP/NP--------------------------
    arcpy.AddMessage('Creating Block Data')
    if PlannedBlock == 'No':
        whereBlock = '''CUTB_BLOCK_STATE IN ('ADV','LC','HB')''' #+ ''' AND  + '''HVS_STATUS_DATE >= timestamp '''+ "'" + str(filterYear) + '-01-01 12:00:00' + "'"
    elif PlannedBlock == 'WIP Only':
        whereBlock = '''CUTB_BLOCK_STATE IN ('ADV','LC','HB','WIP')'''
    else:
        whereBlock = '''CUTB_BLOCK_STATE IN ('ADV','LC','HB','PP','WIP')'''

    arcpy.AddMessage(whereBlock)
    

    selectBlock = 'BctsBlockSelection'
    arcpy.management.MakeFeatureLayer('bctsBlocks_Clip',selectBlock,whereBlock)
    
    whereSu = "STUN_ID IN ('WTRA','WTP','NP','INTRES','OTHER')"
    selectSu = 'SuSelection'

    arcpy.management.MakeFeatureLayer('bctsSU_Clip',selectSu,whereSu)

    erasedBCTSBlocks = 'bctsBlocks_Erased'
    arcpy.analysis.Erase(selectBlock,selectSu,erasedBCTSBlocks)

    #add capacity to add own planned blocks feature class if not in LRM yes
    if PlannedBlockFeatureClass in ('', '#', None):
        pass
    else:
        #clip planned blocks to watershed
        plannedBlocks_Clip = 'plannedBlocks_Clip'
        arcpy.analysis.PairwiseClip(PlannedBlockFeatureClass, watershedFeature, plannedBlocks_Clip)
        
        #merge with erasedBCTSBlocks
        mergedBCTSBlocks = 'bctsBlocks_Merged_Planned'
        arcpy.management.Merge([erasedBCTSBlocks, plannedBlocks_Clip], mergedBCTSBlocks)

        erasedBCTSBlocks = mergedBCTSBlocks
    


    #---------------- Create a Non-recovering layer ----------------------
    # will erase this from the recovering layers 
    nonRecoveringMerged = 'nonRecoveringMerged'
    arcpy.management.Merge([clippedBufferRoads, clippedBufferPipelines_Erased, clippedBufferTransmission_Erased, bufferedRW_Erased, privateLand_Erased], nonRecoveringMerged)

    #--------------------Remove BCTS blocks from consolidated blocks to account of overlap ------------
    ConBlocksNoBCTS = 'consolidatedBlock_Erased_BCTS'
    arcpy.analysis.Erase('consolidatedBlocks_Clip','bctsBlocks_Clip',ConBlocksNoBCTS) 


    #------------------------ Young VRI--------------------------
    youngVRIqueried = 'youngVRIqueried'
    whereVRI = "PROJ_AGE_1 < 40"
    arcpy.management.MakeFeatureLayer('vri_Clip',youngVRIqueried,whereVRI)
    youngVRIerased = 'youngVRIerased'
    arcpy.analysis.Erase(youngVRIqueried,erasedBCTSBlocks,youngVRIerased)
    youngVRIerased2 = 'youngVRIerased2'
    arcpy.analysis.Erase(youngVRIerased,mergeFires,youngVRIerased2)
    youngVRIerased3 = 'youngVRIerased3'
    arcpy.analysis.Erase(youngVRIerased2,ConBlocksNoBCTS,youngVRIerased3)
    youngVRIerased4 = 'youngVRIerased4'
    arcpy.analysis.Erase(youngVRIerased3,mergePests,youngVRIerased4)
    youngVRI = 'youngVRI'
    arcpy.management.Dissolve(youngVRIerased3, youngVRI, ['PROJ_HEIGHT_1','PROJ_AGE_1','SITE_INDEX'])


    #-------------------------------------------------------------------------Calculate ECA and Create Disturbance Layers ------------------------------------------------------------------------------------------- 
    class Factor: #a landscape disturbance factor that contributes to ECA.

        def __init__(self, name: str, featureClass: str, type: str, startingPercent: int = 0) -> None:
            self.featureClass = featureClass
            self.type = type 
            self.name = name
            
            #Create a field for the Source
            arcpy.management.AddField(self.featureClass,'Origin','TEXT')
            arcpy.management.CalculateField(self.featureClass, 'Origin', '"'+self.name +'"', "PYTHON3")
            #create field of interest for factors that have an attribute field that adjusts starting percent
            arcpy.management.AddField(self.featureClass,'FieldOI','TEXT')
            if self.name == 'fire':
                arcpy.management.CalculateField(self.featureClass, 'FieldOI', '!BURN_SEVERITY_RATING!', "PYTHON3")
            elif self.name == 'pest':
                arcpy.management.CalculateField(self.featureClass, 'FieldOI', '!PEST_SEVERITY_DESC!', "PYTHON3")
            else:
                arcpy.management.CalculateField(self.featureClass, 'FieldOI', '"N/A"', "PYTHON3")

            arcpy.management.AddField(self.featureClass,'YearofDisturbance','TEXT',field_length=25)

            if self.type == 'recovering':      
                #add a field to put starting percentage in
                arcpy.management.AddField(self.featureClass, 'StartingPercent','SHORT')

                if self.name == 'pest':
                    #set percentage based on burn severity desc
                    with arcpy.da.UpdateCursor(self.featureClass,['PEST_SEVERITY_DESC','StartingPercent']) as cursor:  
                        for row in cursor:
                            severity = row[0]
                            if severity == 'Trace':
                                row[1] = 1
                            elif severity == 'Light':
                                row[1] = 5
                            elif severity == 'Moderate':
                                row[1] = 20
                            elif severity == 'Severe':
                                row[1] = 40
                            elif severity == 'Very Severe':
                                row[1] = 60
                            cursor.updateRow(row)

                elif self.name == 'consolidatedBlk' or self.name == 'bctsBlk':
                    with arcpy.da.UpdateCursor(self.featureClass,['StartingPercent']) as cursor:  
                        for row in cursor:
                                row[0] = 100
                                cursor.updateRow(row)

                elif self.name == 'fire':
                    with arcpy.da.UpdateCursor(self.featureClass,['BURN_SEVERITY_RATING','StartingPercent','FIRE_SIZE_HECTARES']) as cursor:
                        for row in cursor:
                            severity = row[0]
                            if severity == 'Unburned':
                                row[1] = 0
                            elif severity == 'Low':
                                row[1] = 10
                            elif severity == 'Medium':
                                row[1] = 50
                            elif severity == 'High':
                                row[1] = 80
                            elif row[2] > 0: #null values, where there is a fire but no burn severity data.  Either pre-2015 or wasn't processed
                                row[1] = 100 
                            cursor.updateRow(row)

                elif self.name == 'vri':
                    pass

                else:
                    arcpy.AddMessage('Missing Something')


            #===================================================================================
            #erase non-recovering from recovering 
            #===================================================================================
            if self.type == 'recovering':
                featureclassErased = name + "_erased"
                arcpy.analysis.Erase(self.featureClass, nonRecoveringMerged, featureclassErased) 
            
            #===================================================================================
            # identity to H60
            #===================================================================================
            identityFc = os.path.join(geodatabase, 'Upper_H60')
            featureclassIdH60 = name + "_id_H60"
            if self.type == 'recovering':        
                arcpy.analysis.Identity(featureclassErased,identityFc,featureclassIdH60)
            else:
                arcpy.analysis.Identity(self.featureClass,identityFc,featureclassIdH60)

            #add above/below
            inField = 'Above_H60'
            arcpy.AddField_management(featureclassIdH60,inField,'TEXT')
            
            H60Field = 'FID_Upper_H60'
            fieldList = [inField,H60Field]
            with arcpy.da.UpdateCursor(featureclassIdH60,fieldList) as cursor:
                for row in cursor:
                    if row[1] >= 0:
                        row[0] = 'Yes'
                    else:
                        row[0] = 'No'
                    cursor.updateRow(row)

            #===================================================================================     
            # identity to VRI for site index
            #===================================================================================
            # featureclassIdVRI = os.path.join(geodatabase, name + "_Final")
            featureclassIdVRI = name + "_Final"
            if self.name == 'vri':
                arcpy.conversion.ExportFeatures(featureclassIdH60, featureclassIdVRI)
            else:
                arcpy.analysis.Identity(featureclassIdH60,vri_siteIndex,featureclassIdVRI) 

            #===================================================================================     
            # identity to subbasins
            #===================================================================================
            if subBasin == 'Yes':
                # featureclassReady = os.path.join(geodatabase, name + "_subbasins_Final")
                featureclassReady = name + "_subbasins_Final"
                arcpy.analysis.Identity(featureclassIdVRI,watershedFeature,featureclassReady)
                self.featureClass = featureclassReady
                arcpy.Delete_management(featureclassIdVRI)
            else:
                self.featureClass = featureclassIdVRI


            #===================================================================================           
            # Add ECA Field
            #===================================================================================
            arcpy.management.AddField(self.featureClass,'ECA_Area','DOUBLE')
            arcpy.management.AddField(self.featureClass,'CURR_HEIGHT','FLOAT') #add field for recovered (or current) height
            arcpy.management.AddField(self.featureClass,'ECA_PERCENT','FLOAT')

            #if non recovering, set ECA_PERCENT to starting percent for all polygons
            if self.type == 'nonrecovering':
                arcpy.management.CalculateField(self.featureClass, 'ECA_PERCENT', startingPercent, "PYTHON3")

            if self.name == 'vri':
                arcpy.management.CalculateField(self.featureClass, 'CURR_HEIGHT', '!PROJ_HEIGHT_1!', "PYTHON3") #set current height to PROJ_HEIGHT_1
                

        def recover(self,yearofDistFields) -> None: #outputs a height\

            arcpy.AddMessage('Recovering ' + self.name)
            
            if self.type == 'recovering': #if this factor recovers over time
                
                # add ['CURR_HEIGHT'] to end of list
                yearofDistFields.append('CURR_HEIGHT')
                growth = growthFactor #+ 0.35

                #add common field for merging all factors together at end, admin work doesn't affect calculation
                yearofDistFields.append('YearofDisturbance')

                if self.name == 'bctsBlk': #two fields needed

                    with arcpy.da.UpdateCursor(self.featureClass,yearofDistFields) as cursor: #yearofDistFields will look like ['HVS_STATUS_DATE','HVS_STATUS','CURR_HEIGHT','YearofDisturbance'] for bctsBlk
                        for row in cursor:
                            if row[1] == 'P':
                                startYear = assessYear  
                            else:
                                plantedYear = int(row[0].year) + 2
                                if plantedYear > assessYear:
                                    startYear = assessYear
                                else:
                                    startYear = plantedYear

                            currentHeight = row[2]
                            growthYears = assessYear - startYear
                            row[2] = growth * growthYears
                            row[3] = startYear #for merge at end
                            cursor.updateRow(row)
             
                else: 
                    #calculate growth since disturbance.  For cutblocks, this will be the current height.  want a better growth curve for this -                                             FIND THIS
                    with arcpy.da.UpdateCursor(self.featureClass,yearofDistFields) as cursor: #yearofDistFields will look like ['FIREYEAR','CURR_HEIGHT','YearofDisturbance]
                        for row in cursor:
                            startYear = row[0]
                            currentHeight = row[1]
                            growthYears = assessYear - startYear
                            row[1] = growth * growthYears
                            row[2] = startYear #for merge at end
                            cursor.updateRow(row)



            if self.name == 'fire' or self.name == 'pest':

                # For pest and burn severity, add growth since disturbance to starting height based on ECA percent....only way to do this.
                ecaPercentageFields = ['SITE_INDEX', 'StartingPercent','CURR_HEIGHT']
                with arcpy.da.UpdateCursor(self.featureClass,ecaPercentageFields) as cursor:
                    for row in cursor:
                        SI = row[0]
                        height = row[2]
                        startingPercent = row[1]

                        if SI is None:
                            SI = 12

                        if SI >= 12: #stands expected to reach 25m
                            if startingPercent == 0:
                                startingHeightBasedonPercent = 25
                            else:
                                startingHeightBasedonPercent = 2 - (1 / 0.27) * math.log(1 - ((100 - startingPercent) / 100) ** (1 / 4)) 
                        
                        if SI < 12: #trees expected to only reach 20m
                            startingHeightBasedonPercent = 2 - (1 / 0.3) * math.log(1 - ((100 - startingPercent) / 100) ** 0.34)

                        heightUpdated = height + startingHeightBasedonPercent
                        row[2] = heightUpdated
                        cursor.updateRow(row)


      
        def calculateECApercentage(self): #outputs a percentage
            """
            Calculate y based on the Chapman Richards model detailed by Winkler and Boon (2015)
            
            Parameters:
                height in meters (float): the input value for x

            Returns:
                float: The calculated ECA value, as a decimal
            """
            arcpy.AddMessage('Calculating ECA percent for ' + self.name)

            ecaPercentageFields = ['SITE_INDEX', 'CURR_HEIGHT', 'ECA_PERCENT']
            with arcpy.da.UpdateCursor(self.featureClass,ecaPercentageFields) as cursor:
                for row in cursor:
                    SI = row[0]
                    height = int(row[1])
                    ecaPercent = row[2]

                    if SI is None:
                        SI = 12

                    if SI >= 12: #stands expented to reach 25m
                        if height > 2:
                            ecaPercent = 100 - (100 * (1 - math.exp(-0.27 * (height - 2))) ** (1 / (1 - 0.75))) 
                        else: 
                            ecaPercent= 100
                    
                    if SI < 12:  #stands expected to only reach 20m
                        if height > 2:
                            ecaPercent = 100 - (100 * (1 - math.exp(-0.3 * (height - 2))) ** (1 / (1 - 0.66)))
                        else: 
                            ecaPercent= 100

                    row[2] = ecaPercent
                    cursor.updateRow(row)


        def calculateECAarea(self): #outputs an area

            arcpy.AddMessage('Calculating ECA area for ' + self.name)

            updateFields = ['Above_H60','SHAPE@AREA','ECA_Area','ECA_PERCENT']

            with arcpy.da.UpdateCursor(self.featureClass,updateFields) as cursor:
                for row in cursor:
                    hectares = row[1] / 10000
                    ecaPercentage = row[3]
                    ecaHectares = ecaPercentage/100 * hectares 
            
                    if row[0] == 'Yes': #above the 60% elevation line.  This is where the issues is, h60 adjustment should not exceed total disturbed hectares  
                        h60adjustment = (ecaHectares * 1.5)
                        if h60adjustment >= hectares:
                            ecaHectares = hectares
                        else:
                            ecaHectares = (ecaHectares * 1.5)
            
                    row[2] = ecaHectares

                    cursor.updateRow(row)

            if subBasin == 'Yes':
                dissolveFields = ['Origin','Above_H60',subBasinName,'ECA_PERCENT','ECA_Area','YearofDisturbance','FieldOI']                   
            else:
                dissolveFields = ['Origin','Above_H60','ECA_PERCENT','ECA_Area','YearofDisturbance','FieldOI']

            dissolvedECA = self.name + "ECA"
            arcpy.analysis.PairwiseDissolve(self.featureClass, dissolvedECA, dissolveFields)
            self.featureClass = dissolvedECA


    # ============================================================================
    # create instances of Factors class for each ECA factor   
    # ============================================================================
    arcpy.AddMessage('Adding Roads ECA Factor')
    roads = Factor('rd',clippedBufferRoads,'nonrecovering',100)
    roads.calculateECAarea()

    arcpy.AddMessage('Adding Railways ECA Factor')
    railways = Factor('rail',bufferedRW_Erased,'nonrecovering',100)
    railways.calculateECAarea()

    arcpy.AddMessage('Adding Transmission Lines ECA Factor')
    transmissionLines = Factor('tranL',clippedBufferTransmission_Erased,'nonrecovering',100)
    transmissionLines.calculateECAarea()

    arcpy.AddMessage('Adding Pipelines ECA Factor')
    pipelines = Factor('pipeL',clippedBufferPipelines_Erased,'nonrecovering',100)
    pipelines.calculateECAarea()
    
    arcpy.AddMessage('Adding Private Land ECA Factor')
    privateLand = Factor('private',privateLand_Erased,'nonrecovering',75)
    privateLand.calculateECAarea()
    # end of nonrecovering
    #--------------------------------------------------
                     
    arcpy.AddMessage('Adding Pests ECA Factor')
    pests = Factor('pest',mergePests,'recovering')
    pests.recover(['CAPTURE_YEAR'])
    pests.calculateECApercentage()
    pests.calculateECAarea()

    arcpy.AddMessage('Adding Consolidate Blocks ECA Factor')
    conBlocks = Factor('consolidatedBlk',ConBlocksNoBCTS,'recovering')
    conBlocks.recover(['HARVEST_START_YEAR_CALENDAR'])
    conBlocks.calculateECApercentage()
    conBlocks.calculateECAarea()

    arcpy.AddMessage('Adding BCTS Blocks ECA Factor')
    bctsBlocks = Factor('bctsBlk',erasedBCTSBlocks,'recovering')
    bctsBlocks.recover(['HVS_STATUS_DATE','HVS_STATUS'])
    bctsBlocks.calculateECApercentage()
    bctsBlocks.calculateECAarea()

    #Fire prep: erase burn severity from fires.  Burn severity starts in 2015
    firesMinusBS = 'firesMinusBS'
    arcpy.Erase_analysis(mergeFires,mergeBurnSeverity,firesMinusBS)
    #merge burn severity and fires.  both still have 'FIRE_YEAR' field
    mergeBSandFires = 'mergeBSandFires'
    arcpy.management.Merge([firesMinusBS,mergeBurnSeverity],mergeBSandFires)

    arcpy.AddMessage('Adding Fires ECA Factor')
    fires = Factor('fire',mergeBSandFires,'recovering') 
    fires.recover(['FIRE_YEAR'])
    fires.calculateECApercentage()
    fires.calculateECAarea()

    arcpy.AddMessage('Adding Young VRI ECA Factor')
    youngVRIareas = Factor('vri',youngVRI,'recovering') 
    youngVRIareas.calculateECApercentage() 
    youngVRIareas.calculateECAarea()
    

    #=============================================================================
    # merge factor objects into one.  All the dissolved ECA feature classes, e.g. rdECA, fireECA, etc.
    #=============================================================================
    arcpy.AddMessage('Merging Factors into one feature class')
    dataList = []
    import gc
    for obj in gc.get_objects(): #get all factor objects
        if isinstance(obj,Factor):
            dataList.append(obj.featureClass)

    # DisturbanceLayer = 'ECA_DisturbanceLayer'
    DisturbanceLayer = os.path.join(geodatabase, 'ECA_DisturbanceLayer')
    arcpy.management.Merge(dataList,DisturbanceLayer)



    #=============================================================================
    # account for areas where multiple factors overlap (pests particularily) to create an ECA of over 100%
    #=============================================================================
    # establish intermediate names
    ECAcheck100_Intermediate = 'ECA_DL_Check100_Intermediate'
    ECAcheck100_Intermediate1 = 'ECA_DL_Check100_Intermediate1'
    ECAcheck100_Intermediate2 = 'ECA_DL_Check100_Intermediate2'
    ECAcheck100 = 'ECA_DL_Check100' 
    ECA_DisturbanceIntersected = 'ECA_DisturbanceIntersected'
        

    # intersect to find overlapping polygons, then go through a series of steps that will results in a feature class where shared boundaries have a unique ID
    arcpy.analysis.Intersect(in_features=DisturbanceLayer, out_feature_class=ECAcheck100_Intermediate) 
    arcpy.management.CopyFeatures(ECAcheck100_Intermediate, ECA_DisturbanceIntersected) #will use later

    arcpy.management.DeleteIdentical(in_dataset=ECAcheck100_Intermediate,fields="Shape")
    arcpy.management.CalculateField(in_table=ECAcheck100_Intermediate, field="Boundary", expression='"B"+str(!OBJECTID!)', expression_type="PYTHON3")
    arcpy.analysis.PairwiseDissolve(in_features=ECAcheck100_Intermediate, out_feature_class=ECAcheck100_Intermediate1, dissolve_field="Boundary", statistics_fields=None, multi_part="MULTI_PART")

    # identity back to get ECA_PERCENT for overlapping features
    arcpy.analysis.Identity(in_features=ECA_DisturbanceIntersected, identity_features=ECAcheck100_Intermediate1, out_feature_class=ECAcheck100_Intermediate2)

    # dissolve based on an attribute field that groups together identical polygons
    ECAcheck100 = os.path.join(geodatabase, 'ECA_DL_Check100')
    arcpy.analysis.PairwiseDissolve(in_features=ECAcheck100_Intermediate2, out_feature_class=ECAcheck100, dissolve_field="Boundary", statistics_fields="ECA_PERCENT SUM")

    #=============================================================================
    # identity to subbasins if needed
    #=============================================================================
    if subBasin == 'Yes':
        ECAcheck100_subbasins = os.path.join(geodatabase, 'ECA_DL_Check100_Subbasins')
        arcpy.analysis.Identity(in_features=ECAcheck100, identity_features=watershedFeature, out_feature_class=ECAcheck100_subbasins)
        ECAcheck100 = ECAcheck100_subbasins
    
    #grab disturbance area from here, will be used later to prevent overcounting total disturbed
    global disturbance_area_final
    
    if subBasin == 'Yes':
        # Create dictionary to store disturbance area by sub-basin
        disturbance_area_final = {}
        with arcpy.da.SearchCursor(ECAcheck100, ['Shape_Area', subBasinName]) as cursor:
            for row in cursor:
                basin = row[1]
                area = float(row[0]) / 10000
                if basin in disturbance_area_final:
                    disturbance_area_final[basin] += area
                else:
                    disturbance_area_final[basin] = area
        
        # Calculate total for all basins
        total_disturbance = sum(disturbance_area_final.values())
        arcpy.AddMessage('Total Disturbance Area (ha): ' + str(round(total_disturbance, 2)))
    else:
        disturbanceArea = 0
        with arcpy.da.SearchCursor(ECAcheck100, ['Shape_Area']) as cursor:
            for row in cursor:
                disturbanceArea += float(row[0])

        disturbance_area_final = disturbanceArea / 10000
        arcpy.AddMessage('Total Disturbance Area (ha): ' + str(round(disturbance_area_final, 2)))

 
    # select those with over 100% ECA
    arcpy.management.SelectLayerByAttribute(in_layer_or_view=ECAcheck100, selection_type="NEW_SELECTION", where_clause="SUM_ECA_PERCENT > 100")
    over100count = int(arcpy.management.GetCount(ECAcheck100).getOutput(0))
    if over100count > 0:
        arcpy.AddMessage('Adjusting areas with over 100% ECA')
        #calculate adjustment factor
        arcpy.management.AddField(ECAcheck100, "ADJUST_FACTOR", "FLOAT")
        with arcpy.da.UpdateCursor(ECAcheck100, ['SUM_ECA_PERCENT','ADJUST_FACTOR']) as cursor:
            for row in cursor:
                totalECA = row[0]
                if totalECA > 100:
                    adjustmentFactor = 100 / totalECA
                    row[1] = adjustmentFactor
                else:
                    row[1] = 1
                cursor.updateRow(row)


    #join adjustment factor back to main ECA layer
    DisturbanceLayer_with_adjustment = os.path.join(geodatabase, 'DisturbanceLayer_Adjusted')
    arcpy.analysis.Intersect(in_features=[DisturbanceLayer, ECAcheck100], out_feature_class=DisturbanceLayer_with_adjustment)


    #add adjusted ECA fields
    arcpy.management.AddField(DisturbanceLayer_with_adjustment, "ECA_PERCENT_ADJ", "FLOAT")
    arcpy.management.AddField(DisturbanceLayer_with_adjustment, "ECA_Area_ADJ", "DOUBLE")

    #select features with adjustment factor and calculate adjusted ECA values
    DisturbanceLayer_selection = arcpy.management.SelectLayerByAttribute(in_layer_or_view=DisturbanceLayer_with_adjustment, selection_type="NEW_SELECTION", where_clause="ADJUST_FACTOR IS NOT NULL")

    arcpy.management.CalculateField(in_table=DisturbanceLayer_selection, field="ECA_PERCENT_ADJ", expression="!ECA_PERCENT! * !ADJUST_FACTOR!", expression_type="PYTHON3")
    arcpy.management.CalculateField(in_table=DisturbanceLayer_selection, field="ECA_Area_ADJ", expression="!ECA_PERCENT_ADJ!/100 * !Shape_Area!/10000", expression_type="PYTHON3")

        

    #round ECA_PERCENT_ADJ to 3 decimal places (or 1 decimal place - 17.1% or 0.171)
    arcpy.management.CalculateField(in_table=DisturbanceLayer_with_adjustment, field="ECA_PERCENT_ADJ", expression="Round($feature.ECA_PERCENT_ADJ,3)", expression_type="ARCADE")

    mergedECA = os.path.join(geodatabase, 'MergedECA')
    if subBasin == 'Yes':
        arcpy.management.Dissolve(in_features=DisturbanceLayer_with_adjustment, out_feature_class=mergedECA, dissolve_field=["Origin","ECA_PERCENT", "ECA_PERCENT_ADJ","Above_H60","YearofDisturbance","FieldOI",subBasinName], statistics_fields="ECA_Area_ADJ SUM", multi_part="MULTI_PART")
    else:
        arcpy.management.Dissolve(in_features=DisturbanceLayer_with_adjustment, out_feature_class=mergedECA, dissolve_field=["Origin","ECA_PERCENT", "ECA_PERCENT_ADJ","Above_H60","YearofDisturbance","FieldOI"], statistics_fields="ECA_Area_ADJ SUM", multi_part="MULTI_PART")
            
    
    return mergedECA


# ========================================= MAIN ========================================= 
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
PlannedBlockFeatureClass = arcpy.GetParameterAsText(10)

# env.workspace = geodatabase
arcpy.env.workspace = 'in_memory'
env.overwriteOutput = True

disturbance_area_final = 0  #set here, because not carried over in feature class

arcpy.management.ClearWorkspaceCache() #clean personal arcpro temp folder
delete()

#----------------------------Create H60 Data ---------------------------------------
arcpy.AddMessage('Creating H60 Data')  
createH60(DEM, geodatabase)

createData(bcgwConnection,dbp06Connection,watershed,subBasin,subBasinName,growthFactor,assessYear,PlannedBlock, PlannedBlockFeatureClass)

#=============================================================================
# Get the geodatabase name to name the output spreadsheet after it
#=============================================================================
# Get just the last part of the path (Anzac.gdb)
gdb_name_with_ext = os.path.basename(geodatabase)

# Strip the .gdb extension
gdb_name = os.path.splitext(gdb_name_with_ext)[0]

#=============================================================================
#write data to output excel sheet
#=============================================================================
mergedECAFeatureClass = geodatabase + "\MergedECA"
writetoExcel(watershed,mergedECAFeatureClass,subBasin,subBasinName,gdb_name)

arcpy.AddMessage('Removing Un-needed Data') 
delete()
arcpy.Delete_management("in_memory")
arcpy.AddMessage('Finished')
    
 
#TO DO
# better growth curves