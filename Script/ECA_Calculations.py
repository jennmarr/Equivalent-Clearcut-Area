import arcpy,os, csv
from arcpy import env
from datetime import datetime

def addField(inFc,field,fieldType,gdb):
    env.workspace = gdb
    arcpy.management.AddField(inFc,field,fieldType)

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

def sumerizeData(watershed,inBlock,inRoad,inConBlock,inFireBlock,gdb,subBasin,subBasinName,ScriptPath):
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


    csvName = 'ECA_Summary.csv'
    csvFile = os.path.join(ScriptPath,csvName)

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

def CalculateECA(growth,inBlock,inRoad,inConBlock,inFireBlock,watershed,assessYear,gdb,subBasin,subBasinName,ScriptPath):
    print('Blocks')
    bctsBlockECA(growth,inBlock,assessYear,gdb)
    print('Roads')
    roadECA(inRoad,gdb)
    print('ConBlock')
    consolidatedBlockECA(inConBlock,growth,assessYear,gdb)
    print('Fire')
    fireECA(inFireBlock,growth,assessYear,gdb)
    print('Summary')
    sumerizeData(watershed,inBlock,inRoad,inConBlock,inFireBlock,gdb,subBasin,subBasinName,ScriptPath)