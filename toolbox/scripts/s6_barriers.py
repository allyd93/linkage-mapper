#!/usr/bin/env python2.5
# Author: Brad McRae

"""Detects influential barriers given CWD calculations from
    Linkage Mapper step 3.
Reguired Software:
ArcGIS 10 with Spatial Analyst extension
Python 2.6
Numpy
"""

import os.path as path

import arcpy
from arcpy.sa import *
import numpy as npy

from lm_config import tool_env as cfg
import lm_util as lu

# Writing to tifs allows long filenames, needed for large radius values.
# Virtually no speed penalty in this case based on tests with large dataset.
tif = '.tif'


_SCRIPT_NAME = "s6_barriers.py"


def STEP6_calc_barriers():
    """Detects influential barriers given CWD calculations from
       s3_calcCwds.py.

    """

# Fixme: add option to save individual barrier files?
    gprint = lu.gprint
    try:
        #cfg.SUM_BARRIERS = True
        arcpy.CheckOutExtension("spatial")

        lu.dashline(0)
        gprint('Running script ' + _SCRIPT_NAME)

        
        if cfg.SUM_BARRIERS:
            sumSuffix = '_sum'
            cfg.BARRIERBASEDIR = cfg.BARRIERBASEDIR + sumSuffix
            baseName, extension = path.splitext(cfg.BARRIERGDB)
            cfg.BARRIERGDB = baseName + sumSuffix + extension

            gprint('\nBarrier scores will be SUMMED across core pairs.')
        else:
            sumSuffix = ''

        # Delete contents of final ouptut geodatabase           
        lu.clean_out_workspace(cfg.BARRIERGDB)
        if not arcpy.Exists(cfg.BARRIERGDB):
            # Create output geodatabase
            arcpy.CreateFileGDB_management(cfg.OUTPUTDIR,
                                           path.basename(cfg.BARRIERGDB))             
                                           
        startRadius = float(cfg.STARTRADIUS)
        endRadius = float(cfg.ENDRADIUS)
        radiusStep = float(cfg.RADIUSSTEP)
        if radiusStep == 0:
            endRadius = startRadius # Calculate at just one radius value
            radiusStep = 1
        linkTableFile = lu.get_prev_step_link_table(step=6)
        arcpy.env.workspace = cfg.SCRATCHDIR
        arcpy.env.scratchWorkspace = cfg.ARCSCRATCHDIR
        arcpy.RefreshCatalog(cfg.PROJECTDIR)
        PREFIX = path.basename(cfg.PROJECTDIR)
        # For speed:
        arcpy.env.pyramid = "NONE"
        arcpy.env.rasterStatistics = "NONE"

        # set the analysis extent and cell size to that of the resistance
        # surface
        arcpy.OverWriteOutput = True
        arcpy.env.extent = cfg.RESRAST
        arcpy.env.cellSize = cfg.RESRAST
        arcpy.env.snapRaster = cfg.RESRAST
        spatialref = arcpy.Describe(cfg.RESRAST).spatialReference                
        mapUnits = spatialref.linearUnitName
        
        
        if float(arcpy.env.cellSize) > startRadius or startRadius > endRadius:
            msg = ('Error: minimum detection radius must be greater than '
                    'cell size (' + str(arcpy.env.cellSize) +
                    ') \nand less than or equal to maximum detection radius.')
            lu.raise_error(msg)

        linkTable = lu.load_link_table(linkTableFile)
        numLinks = linkTable.shape[0]
        numCorridorLinks = lu.report_links(linkTable)
        if numCorridorLinks == 0:
            lu.dashline(1)
            msg =('\nThere are no linkages. Bailing.')
            lu.raise_error(msg)

        # set up directories for barrier and barrier mosaic grids
        dirCount = 0
        gprint("Creating intermediate output folder: " + cfg.BARRIERBASEDIR)
        lu.delete_dir(cfg.BARRIERBASEDIR)
        lu.create_dir(cfg.BARRIERBASEDIR)
        arcpy.CreateFolder_management(cfg.BARRIERBASEDIR, cfg.BARRIERDIR_NM)
        cbarrierdir = path.join(cfg.BARRIERBASEDIR, cfg.BARRIERDIR_NM)

        coresToProcess = npy.unique(linkTable[:, cfg.LTB_CORE1:cfg.LTB_CORE2 + 1])
        maxCoreNum = max(coresToProcess)

        # Set up focal directories.
        # To keep there from being > 100 grids in any one directory,
        # outputs are written to:
        # barrier\focalX_ for cores 1-99 at radius X
        # barrier\focalX_1 for cores 100-199
        # etc.
        lu.dashline(0)

        for radius in range(startRadius, endRadius + 1, radiusStep):
            core1path = lu.get_focal_path(1,radius)
            path1, dir1 = path.split(core1path)
            path2, dir2 = path.split(path1)
            arcpy.CreateFolder_management(path.dirname(path2),
                                       path.basename(path2))
            arcpy.CreateFolder_management(path.dirname(path1),
                                       path.basename(path1))

            if maxCoreNum > 99:
                gprint('Creating subdirectories for ' + str(radius) + ' ' + 
                       str(mapUnits) + ' radius analysis scale.')
                maxDirCount = int(maxCoreNum/100)
                focalDirBaseName = dir2

                cp100 = (coresToProcess.astype('int32'))/100
                ind = npy.where(cp100 > 0)
                dirNums = npy.unique(cp100[ind])
                for dirNum in dirNums:
                    focalDir = focalDirBaseName + str(dirNum)
                    gprint('...' + focalDir)
                    arcpy.CreateFolder_management(path2, focalDir)                        
        
        # Create resistance raster with filled-in Nodata values for later use
        arcpy.env.extent = cfg.RESRAST
        resistFillRaster = path.join(cfg.SCRATCHDIR, "resist_fill")
        output = arcpy.sa.Con(IsNull(cfg.RESRAST), 1000000000, cfg.RESRAST)
        output.save(resistFillRaster)

        numGridsWritten = 0
        coreList = linkTable[:,cfg.LTB_CORE1:cfg.LTB_CORE2+1]
        coreList = npy.sort(coreList)

        # Loop through each search radius to calculate barriers in each link
        import time
        startTime = time.clock()
        for radius in range (startRadius, endRadius + 1, radiusStep):
            linkLoop = 0
            pctDone = 0
            gprint('\nMapping barriers at a radius of ' + str(radius) +
                   ' ' + str(mapUnits))             
            if cfg.SUM_BARRIERS:  
                gprint('using SUM method')
            else:
                gprint('using MAXIMUM method')                   
            if numCorridorLinks > 1:
                gprint('0 percent done')
            lastMosaicRaster = None
            lastMosaicRasterPct = None
            for x in range(0,numLinks):
                pctDone = lu.report_pct_done(linkLoop, numCorridorLinks,
                                            pctDone)
                linkId = str(int(linkTable[x,cfg.LTB_LINKID]))
                if ((linkTable[x,cfg.LTB_LINKTYPE] > 0) and
                   (linkTable[x,cfg.LTB_LINKTYPE] < 1000)):
                    linkLoop = linkLoop + 1
                    # source and target cores
                    corex=int(coreList[x,0])
                    corey=int(coreList[x,1])

                    # Get cwd rasters for source and target cores
                    cwdRaster1 = lu.get_cwd_path(corex)
                    cwdRaster2 = lu.get_cwd_path(corey)
                    focalRaster1 = lu.get_focal_path(corex,radius)
                    focalRaster2 = lu.get_focal_path(corey,radius)
                                              
                    arcpy.env.extent = cfg.RESRAST
                    if not cfg.SUM_BARRIERS:
                        arcpy.env.extent = "MINOF"

                    link = lu.get_links_from_core_pairs(linkTable,
                                                        corex, corey)
                    lcDist = float(linkTable[link,cfg.LTB_CWDIST])
                    
                    # Detect barriers at radius using neighborhood stats
                    # Create the Neighborhood Object
                    innerRadius = radius - 1
                    outerRadius = radius

                    dia = 2 * radius
                    InNeighborhood = ("ANNULUS " + str(innerRadius) + " " +
                                     str(outerRadius) + " MAP")

                    # Execute FocalStatistics
                    if not path.exists(focalRaster1):
                        outFocalStats = arcpy.sa.FocalStatistics(cwdRaster1,
                                            InNeighborhood, "MINIMUM","DATA")
                        outFocalStats.save(focalRaster1)

                    if not path.exists(focalRaster2):
                        outFocalStats = arcpy.sa.FocalStatistics(cwdRaster2,
                                        InNeighborhood, "MINIMUM","DATA")
                        outFocalStats.save(focalRaster2)

                    barrierRaster = path.join(cbarrierdir, "b" + str(radius)
                          + "_" + str(corex) + "_" +
                          str(corey)+'.tif') 
                    #Calculate potential benefit per map unit restored
                    statement = ('outRas = ((lcDist - Raster(focalRaster1) - '
                                 'Raster(focalRaster2) - dia) / dia); '
                                 'outRas.save(barrierRaster)')
                         
                    if cfg.SUM_BARRIERS: # Need to set nulls to 0
                        statement = ('outRas = ((lcDist - Raster(focalRaster1) - '
                                 'Raster(focalRaster2) - dia) / dia);'
                                 'outCon = arcpy.sa.Con(IsNull(outRas),0,outRas); '
                                 'outCon.save(barrierRaster)')

                    count = 0
                    while True:
                        try:
                            exec statement
                        except:
                            count,tryAgain = lu.retry_arc_error(count,statement)
                            if not tryAgain:
                                exec statement
                        else: break
                
                    #Calculate PERCENT potential benefit per map unit restored                        
                    barrierRasterPct = path.join(cbarrierdir, "b" + str(radius)
                          + "_" + str(corex) + "_" +
                          str(corey)+'_pct.tif') 
                    statement = ('outras = (100 * (Raster(barrierRaster) / lcDist)); '
                                 'outras.save(barrierRasterPct)')
                    count = 0
                    while True:
                        try:
                            exec statement
                        except:
                            count,tryAgain = lu.retry_arc_error(count,statement)
                            if not tryAgain:
                                exec statement
                        else: break
                    
                    # Mosaic barrier results across core area pairs                    
                    mosaicDir = path.join(cfg.SCRATCHDIR,'mos'+str(x+1)) 
                    lu.create_dir(mosaicDir)
                    
                    mosFN = 'mos_temp'
                    tempMosaicRaster = path.join(mosaicDir,mosFN)
                    arcpy.env.workspace = mosaicDir            
                    if linkLoop == 1:
                        #If this is the first grid then copy rather than mosaic
                        if cfg.SUM_BARRIERS:
                            outCon = arcpy.sa.Con(Raster(barrierRaster) < 0, 0,
                            arcpy.sa.Con(IsNull(barrierRaster),0,barrierRaster)) 
                            outCon.save(tempMosaicRaster)
                        else:
                            arcpy.CopyRaster_management(barrierRaster, 
                                                        tempMosaicRaster)
                    else:                
                        if cfg.SUM_BARRIERS:
                            statement = ('outCon = arcpy.sa.Con(Raster(barrierRaster) < 0, lastMosaicRaster, Raster(barrierRaster) + Raster(lastMosaicRaster));outCon.save(tempMosaicRaster)')                            #fixme: temp may be nodata                        
                        else:
                            rasterString = '"'+barrierRaster+";"+lastMosaicRaster+'"'
                            statement = ('arcpy.MosaicToNewRaster_management('
                                    'rasterString,mosaicDir,mosFN, "", '
                                    '"32_BIT_FLOAT", arcpy.env.cellSize, "1", "MAXIMUM", '
                                    '"MATCH")') 

                        count = 0
                        while True:
                            try:
                                exec statement
                            except:
                                count,tryAgain = lu.retry_arc_error(count,statement)
                                lu.delete_data(tempMosaicRaster)
                                lu.delete_dir(mosaicDir)
                                # Try a new directory
                                mosaicDir = path.join(cfg.SCRATCHDIR,'mos'+str(x+1) + '_' + str(count)) 
                                lu.create_dir(mosaicDir)
                                arcpy.env.workspace = mosaicDir            
                                tempMosaicRaster = path.join(mosaicDir,mosFN)              
                                if not tryAgain:    
                                    exec statement
                            else: break

                    lastMosaicRaster = tempMosaicRaster
                                 
                    mosPctFN = 'mos_temp_pct'
                    tempMosaicRasterPct = path.join(mosaicDir,mosPctFN)

                    if linkLoop == 1:
                        #If this is the first grid then copy rather than mosaic
                        if cfg.SUM_BARRIERS:
                            outCon = arcpy.sa.Con(Raster(barrierRasterPct) < 0, 0,
                                arcpy.sa.Con(IsNull(barrierRasterPct),0,barrierRasterPct)) 
                            outCon.save(tempMosaicRasterPct)
                        else:
                            arcpy.CopyRaster_management(barrierRasterPct, 
                                                     tempMosaicRasterPct)
                                        
                    else:                
                        if cfg.SUM_BARRIERS:
                            statement = ('outCon = arcpy.sa.Con(Raster(barrierRasterPct) < 0, lastMosaicRasterPct, Raster(barrierRasterPct) + Raster(lastMosaicRasterPct));'
                                         'outCon.save(tempMosaicRasterPct)')
                        else:
                            rasterString = '"'+barrierRasterPct+";"+lastMosaicRasterPct+'"'
                            statement = ('arcpy.MosaicToNewRaster_management('
                                    'rasterString,mosaicDir,mosPctFN, "", '
                                    '"32_BIT_FLOAT", arcpy.env.cellSize, "1", "MAXIMUM", '
                                    '"MATCH")') 
                        
                        count = 0
                        while True:
                            try:
                                exec statement
                            except:
                                count,tryAgain = lu.retry_arc_error(count,statement)
                                if not tryAgain:    
                                    exec statement
                            else: break

                    lu.delete_data(lastMosaicRasterPct)
                    lastMosaicRasterPct = tempMosaicRasterPct                    
                    
                    if not cfg.SAVEBARRIERRASTERS:
                        lu.delete_data(barrierRaster)
                        lu.delete_data(barrierRasterPct)
                        
                        
                    # Temporarily disable links in linktable -
                    # don't want to mosaic them twice
                    for y in range (x+1,numLinks):
                        corex1 = int(coreList[y,0])
                        corey1 = int(coreList[y,1])
                        if corex1 == corex and corey1 == corey:
                            linkTable[y,cfg.LTB_LINKTYPE] = (
                                linkTable[y,cfg.LTB_LINKTYPE] + 1000)
                        elif corex1==corey and corey1==corex:
                            linkTable[y,cfg.LTB_LINKTYPE] = (
                                linkTable[y,cfg.LTB_LINKTYPE] + 1000)

                    if cfg.SAVEBARRIERRASTERS:
                        numGridsWritten = numGridsWritten + 1
                    if numGridsWritten == 100:
                        # We only write up to 100 grids to any one folder
                        # because otherwise Arc slows to a crawl
                        dirCount = dirCount + 1
                        numGridsWritten = 0
                        cbarrierdir = (path.join(cfg.BARRIERBASEDIR,
                                      cfg.BARRIERDIR_NM) + str(dirCount))
                        arcpy.CreateFolder_management(cfg.BARRIERBASEDIR,
                                                   path.basename(cbarrierdir))
            gprint('100 percent done')
            #rows that were temporarily disabled
            rows = npy.where(linkTable[:,cfg.LTB_LINKTYPE]>1000)
            linkTable[rows,cfg.LTB_LINKTYPE] = (
                linkTable[rows,cfg.LTB_LINKTYPE] - 1000)

            # -----------------------------------------------------------------
            
            # Set negative values to null and write geodatabase.
            mosaicFN = PREFIX + "_barriers" + sumSuffix + str(radius)
            arcpy.env.extent = cfg.RESRAST
            outSetNull = arcpy.sa.SetNull(tempMosaicRaster, tempMosaicRaster,
                                          "VALUE < 0")
            mosaicRaster = path.join(cfg.BARRIERGDB, mosaicFN)
            outSetNull.save(mosaicRaster)
            lu.delete_data(tempMosaicRaster)
                           
            # Do same for percent raster
            mosaicPctFN = PREFIX + "_barriers_pct" + sumSuffix + str(radius)
            arcpy.env.extent = cfg.RESRAST
            outSetNull = arcpy.sa.SetNull(tempMosaicRasterPct, tempMosaicRasterPct,
                                          "VALUE < 0")
            mosaicRasterPct = path.join(cfg.BARRIERGDB, mosaicPctFN)
            outSetNull.save(mosaicRasterPct)
            lu.delete_data(tempMosaicRasterPct)
                       
            
            # 'Grow out' maximum restoration gain to
            # neighborhood size for display
            InNeighborhood = "CIRCLE " + str(outerRadius) + " MAP"
            # Execute FocalStatistics
            fillRasterFN = "barriers_fill" + str(outerRadius) + tif
            fillRaster = path.join(cfg.BARRIERBASEDIR, fillRasterFN)
            outFocalStats = arcpy.sa.FocalStatistics(mosaicRaster,
                                            InNeighborhood, "MAXIMUM","DATA")
            outFocalStats.save(fillRaster)

            # Do same for percent raster
            fillRasterPctFN = "barriers_fill_pct" + str(outerRadius) + tif
            fillRasterPct = path.join(cfg.BARRIERBASEDIR, fillRasterPctFN)
            outFocalStats = arcpy.sa.FocalStatistics(mosaicRasterPct,
                                            InNeighborhood, "MAXIMUM","DATA")
            outFocalStats.save(fillRasterPct)
            

            #Place copies of filled rasters in output geodatabase
            arcpy.env.workspace = cfg.BARRIERGDB
            fillRasterFN = PREFIX + "_barrriers_fill" + sumSuffix + str(outerRadius) 
            arcpy.CopyRaster_management(fillRaster, fillRasterFN)
            fillRasterPctFN = PREFIX + "_barrriers_fill_pct" + sumSuffix + str(outerRadius) 
            arcpy.CopyRaster_management(fillRasterPct, fillRasterPctFN)

            if not cfg.SUM_BARRIERS:
                # Create pared-down version of filled raster- remove pixels that
                # don't need restoring by allowing a pixel to only contribute its
                # resistance value to restoration gain
                outRasterFN = "barriers_trm" + str(outerRadius) + tif
                outRaster = path.join(cfg.BARRIERBASEDIR,outRasterFN)
                rasterList = [fillRaster, resistFillRaster]
                outCellStatistics = arcpy.sa.CellStatistics(rasterList, "MINIMUM")
                outCellStatistics.save(outRaster)
        
                #SECOND ROUND TO CLIP BY DATA VALUES IN BARRIER RASTER
                outRaster2FN = "barriers_trm"  + sumSuffix + str(outerRadius) + "_2" + tif
                outRaster2 = path.join(cfg.BARRIERBASEDIR,outRaster2FN)
                output = arcpy.sa.Con(IsNull(fillRaster),fillRaster,outRaster)
                output.save(outRaster2)
                outRasterFN = PREFIX + "_barriers_trm"  + sumSuffix + str(outerRadius)
                outRasterPath= path.join(cfg.BARRIERGDB, outRasterFN)
                arcpy.CopyRaster_management(outRaster2, outRasterFN)
        
            startTime=lu.elapsed_time(startTime)
        
        # Combine rasters across radii
        gprint('\nCreating summary rasters...')
        if startRadius != endRadius:
            mosaicFN = "bar_radii" 
            mosaicPctFN = "bar_radii_pct" 
            arcpy.env.workspace = cfg.BARRIERBASEDIR
            for radius in range (startRadius, endRadius + 1, radiusStep):
                #Fixme: run speed test with gdb mosaicking above and here
                radiusFN = PREFIX + "_barriers" + sumSuffix + str(radius)
                radiusRaster = path.join(cfg.BARRIERGDB, radiusFN)

                if radius == startRadius:
                #If this is the first grid then copy rather than mosaic
                    arcpy.CopyRaster_management(radiusRaster, mosaicFN)
                else:
                    mosaicRaster = path.join(cfg.BARRIERBASEDIR,mosaicFN)

                    arcpy.Mosaic_management(radiusRaster, mosaicRaster,
                                         "MAXIMUM", "MATCH")
                                         
                radiusPctFN = PREFIX + "_barriers_pct" + sumSuffix + str(radius)
                radiusRasterPct = path.join(cfg.BARRIERGDB, radiusPctFN)

                if radius == startRadius:
                #If this is the first grid then copy rather than mosaic
                    arcpy.CopyRaster_management(radiusRasterPct, mosaicPctFN)
                else:
                    mosaicRasterPct = path.join(cfg.BARRIERBASEDIR,mosaicPctFN)

                    arcpy.Mosaic_management(radiusRasterPct, mosaicRasterPct,
                                         "MAXIMUM", "MATCH")
                                        
            # Copy results to output geodatabase
            arcpy.env.workspace = cfg.BARRIERGDB
            mosaicFN = PREFIX + "_barriers_radii" + sumSuffix 
            arcpy.CopyRaster_management(mosaicRaster, mosaicFN)
            
            mosaicPctFN = PREFIX + "_barriers_radii_pct" + sumSuffix 
            arcpy.CopyRaster_management(mosaicRasterPct, mosaicPctFN)
                      
            
            #GROWN OUT rasters
            fillMosaicFN = "barriers_radii_fill" + tif
            fillMosaicPctFN = "barriers_radii_fill_pct" + tif
            fillMosaicRaster = path.join(cfg.BARRIERBASEDIR,fillMosaicFN)
            fillMosaicRasterPct = path.join(cfg.BARRIERBASEDIR,fillMosaicPctFN)
            
            arcpy.env.workspace = cfg.BARRIERBASEDIR
            for radius in range (startRadius, endRadius + 1, radiusStep):
                radiusFN = "barriers_fill" + str(radius) + tif
                #fixme- do this when only a single radius too
                radiusRaster = path.join(cfg.BARRIERBASEDIR, radiusFN)
                if radius == startRadius:
                #If this is the first grid then copy rather than mosaic
                    arcpy.CopyRaster_management(radiusRaster, fillMosaicFN)
                else:
                    arcpy.Mosaic_management(radiusRaster, fillMosaicRaster,
                                         "MAXIMUM", "MATCH")
                                         
                radiusPctFN = "barriers_fill_pct" + str(radius) + tif
                #fixme- do this when only a single radius too
                radiusRasterPct = path.join(cfg.BARRIERBASEDIR, radiusPctFN)
                if radius == startRadius:
                #If this is the first grid then copy rather than mosaic
                    arcpy.CopyRaster_management(radiusRasterPct, fillMosaicPctFN)
                else:
                    arcpy.Mosaic_management(radiusRasterPct, fillMosaicRasterPct,
                                         "MAXIMUM", "MATCH")
                                         
            # Copy result to output geodatabase
            arcpy.env.workspace = cfg.BARRIERGDB
            fillMosaicFN = PREFIX + "_barriers_radii_fill" + sumSuffix 
            arcpy.CopyRaster_management(fillMosaicRaster, fillMosaicFN)
            fillMosaicPctFN = PREFIX + "_barriers_radii_fill_pct" + sumSuffix 
            arcpy.CopyRaster_management(fillMosaicRasterPct, fillMosaicPctFN)
            
            if not cfg.SUM_BARRIERS:
                #GROWN OUT AND TRIMMED rasters (Can't do percent or sum)
                trimMosaicFN = "bar_radii_trm"
                arcpy.env.workspace = cfg.BARRIERBASEDIR
                trimMosaicRaster = path.join(cfg.BARRIERBASEDIR,trimMosaicFN)
                for radius in range (startRadius, endRadius + 1, radiusStep):
                    radiusFN = PREFIX + "_barriers_trm"  + str(radius) 
                    #fixme- do this when only a single radius too
                    radiusRaster = path.join(cfg.BARRIERGDB, radiusFN)

                    if radius == startRadius:
                    #If this is the first grid then copy rather than mosaic
                        arcpy.CopyRaster_management(radiusRaster, trimMosaicFN)
                    else:
                        arcpy.Mosaic_management(radiusRaster, trimMosaicRaster,
                                             "MAXIMUM", "MATCH")
                # Copy result to output geodatabase
                arcpy.env.workspace = cfg.BARRIERGDB
                trimMosaicFN = PREFIX + "_barriers_radii_trm"
                arcpy.CopyRaster_management(trimMosaicRaster, trimMosaicFN)

        arcpy.env.workspace = cfg.BARRIERGDB
        rasters = arcpy.ListRasters()
        for raster in rasters:
            gprint('\nBuilding output statistics and pyramids\n '
                        'for raster ' + raster)
            lu.build_stats(raster)

        #Clean up temporary files and directories
        if not cfg.SAVEBARRIERRASTERS:
            cbarrierdir = path.join(cfg.BARRIERBASEDIR, cfg.BARRIERDIR_NM)
            lu.delete_dir(cbarrierdir)
            for dir in range(1,dirCount+1):
                cbarrierdir = path.join(cfg.BARRIERBASEDIR, cfg.BARRIERDIR_NM
                                        + str(dir)) 
                lu.delete_dir(cbarrierdir)

        if not cfg.SAVEFOCALRASTERS:
            for radius in range(startRadius, endRadius + 1, radiusStep):
                core1path = lu.get_focal_path(1,radius)
                path1, dir1 = path.split(core1path)
                path2, dir2 = path.split(path1)
                lu.delete_dir(path2)

    # Return GEOPROCESSING specific errors
    except arcpy.ExecuteError:
        lu.dashline(1)
        gprint('****Failed in step 6. Details follow.****')
        lu.exit_with_geoproc_error(_SCRIPT_NAME)

    # Return any PYTHON or system specific errors
    except:
        lu.dashline(1)
        gprint('****Failed in step 6. Details follow.****')
        lu.exit_with_python_error(_SCRIPT_NAME)

    return
