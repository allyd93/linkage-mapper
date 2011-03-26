#!/usr/bin/env python2.5

##*****************************************************************
## 2011_0128
## NAME: s5_calcLccs.py
##
## SUMMARY: Creates and mosaics normalized least-cost corridors
## using connected core area pairs specified in linkTable and
## cwd layers
##
## SOFTWARE: ArcGIS 9.3 (requires Spatial Analyst extension)
##           Python 2.5
##
##*****************************************************************

# import required modules
import sys
import os.path as path
import time
import shutil

import arcgisscripting
from numpy import *

from lm_config import Config as Cfg
import lm_util as lu

def STEP5_calc_lccs():
    """Creates and mosaics normalized least-cost corridors
    using connected core area pairs specified in linkTable and
    cwd layers

    """

# Fixme: add option to saveRawLccs? Or mosaicLccs that already exist?
    try:
        linkTableFile = lu.get_prev_step_link_table(step=5)
        Cfg.gp.workspace = Cfg.SCRATCHDIR

        if Cfg.MAXEUCDIST is not None:
            Cfg.gp.addmessage('Max Euclidean distance between cores')
            Cfg.gp.addmessage('for linkage mapping set to ' +
                              str(Cfg.MAXEUCDIST))

        if Cfg.MAXCOSTDIST is not None:
            Cfg.gp.addmessage('Max cost-weighted distance between cores')
            Cfg.gp.addmessage('for linkage mapping set to ' +
                              str(Cfg.MAXCOSTDIST))


        # set the analysis extent and cell size to that of the resistance
        # surface
        Cfg.gp.Extent = Cfg.gp.Describe(Cfg.RESRAST).Extent
        Cfg.gp.CellSize = Cfg.gp.Describe(Cfg.RESRAST).MeanCellHeight
        Cfg.gp.Extent = "MINOF"
        Cfg.gp.mask = Cfg.RESRAST
        Cfg.gp.snapraster = Cfg.RESRAST

        linkTable = lu.load_link_table(linkTableFile)
        numLinks = linkTable.shape[0]
        lu.report_links(linkTable)

        if not Cfg.STEP3 and not Cfg.STEP4:
            # re-check for links that are too long or in case script run out of
            # sequence with more stringent settings
            Cfg.gp.addmessage('Double-checking for corridors that are too long'
                              ' to map.')
            disableLeastCostNoVal = True
            linkTable,numDroppedLinks = lu.drop_links(
                linkTable, Cfg.MAXEUCDIST, Cfg.MINEUCDIST, Cfg.MAXCOSTDIST,
                Cfg.MINCOSTDIST, disableLeastCostNoVal)

        # Added to try to speed up:
        Cfg.gp.pyramid = "NONE"
        Cfg.gp.rasterstatistics = "NONE"

        # set up directories for normalized lcc and mosaic grids
        dirCount = 0
        Cfg.gp.addmessage("Creating output folder: " + Cfg.LCCBASEDIR)
        if path.exists(Cfg.LCCBASEDIR):
            shutil.rmtree(Cfg.LCCBASEDIR)
        Cfg.gp.CreateFolder_management(path.dirname(Cfg.LCCBASEDIR),
                                       path.basename(Cfg.LCCBASEDIR))
        Cfg.gp.CreateFolder_management(Cfg.LCCBASEDIR, Cfg.LCCNLCDIR_NM)
        clccdir = path.join(Cfg.LCCBASEDIR, Cfg.LCCNLCDIR_NM)
        Cfg.gp.CreateFolder_management(Cfg.LCCBASEDIR,
                                       path.basename(Cfg.LCCMOSAICDIR))
        mosaicRaster = path.join(Cfg.LCCMOSAICDIR, "nlcc_mos")
        Cfg.gp.addmessage('\nNormalized Least-cost corridors will be written '
                          'to ' + clccdir + '\n')

        # Add CWD layers for core area pairs to produce NORMALIZED LCC layers
        numGridsWritten = 0
        coreList = linkTable[:,Cfg.LTB_CORE1:Cfg.LTB_CORE2+1]
        coreList = sort(coreList)

        for x in range(0,numLinks):
            linkId = str(int(linkTable[x,Cfg.LTB_LINKID]))

            if (linkTable[x,Cfg.LTB_LINKTYPE] == Cfg.LT_CORR or
                linkTable[x,Cfg.LTB_LINKTYPE] == Cfg.LT_CLU):
                # source and target cores
                corex=int(coreList[x,0])
                corey=int(coreList[x,1])

                # Get cwd rasters for source and target cores
                cwdRaster1 = lu.get_cwd_path(corex)
                cwdRaster2 = lu.get_cwd_path(corey)

                lccNormRaster = path.join(clccdir, str(corex) + "_" +
                                          str(corey))
                Cfg.gp.Extent = "MINOF"

                # FIXME: need to check for this?:
                # if exists already, don't re-create
                #if not Cfg.gp.Exists(lccRaster):

                link = lu.get_links_from_core_pairs(linkTable, corex, corey)
                lcDist = str(linkTable[link,Cfg.LTB_CWDIST])

                # Normalized lcc rasters are created by adding cwd rasters and
                # subtracting the least cost distance between them.
                expression = cwdRaster1 + " + " + cwdRaster2 + " - " + lcDist
                count = 0
                statement = ('Cfg.gp.SingleOutputMapAlgebra_sa(expression, '
                            'lccNormRaster)')
                startTime = time.clock()
                while True:
                    try: exec statement
                    except:
                        count,tryAgain = lu.hiccup_test(count,statement)
                        if not tryAgain: exec statement
                    else: break

                Cfg.gp.Extent = "MAXOF"
                if numGridsWritten == 0 and dirCount == 0:
                    #If this is the first grid then copy rather than mosaic
                    Cfg.gp.CopyRaster_management(lccNormRaster, mosaicRaster)
                else:
                    # Note: cannot use SOMA to mosaic. It is a different
                    # process entirely.
                    count = 0
                    statement = ('Cfg.gp.Mosaic_management(lccNormRaster, '
                                 'mosaicRaster, "MINIMUM", "MATCH")')
                    while True:
                        try: exec statement
                        except:
                            count,tryAgain = lu.hiccup_test(count,statement)
                            if not tryAgain: exec statement
                        else: break

                endTime = time.clock()
                processTime = round((endTime - startTime), 2)
                Cfg.gp.addmessage("Normalized and mosaicked corridor for link "
                                  "#" + str(linkId)
                                  + " connecting core areas " + str(corex) +
                                  " and " + str(corey)+ " in " +
                                  str(processTime) + " seconds.")

                if not Cfg.SAVENORMLCCS:
                    Cfg.gp.delete_management(lccNormRaster)

                # temporarily disable links in linktable - don't want to mosaic
                # them twice
                for y in range (x+1,numLinks):
                    corex1 = int(coreList[y,0])
                    corey1 = int(coreList[y,1])
                    if corex1 == corex and corey1 == corey:
                        linkTable[y,Cfg.LTB_LINKTYPE] = (
                            linkTable[y,Cfg.LTB_LINKTYPE] + 100)
                    elif corex1==corey and corey1==corex:
                        linkTable[y,Cfg.LTB_LINKTYPE] = (
                            linkTable[y,Cfg.LTB_LINKTYPE] + 100)


                numGridsWritten = numGridsWritten + 1
                if Cfg.SAVENORMLCCS:
                    if numGridsWritten == 100:
                        # We only write up to 100 grids to any one folder
                        # because otherwise Arc slows to a crawl
                        dirCount = dirCount + 1
                        numGridsWritten = 0
                        clccdir = path.join(clccdir, str(dirCount))
                        Cfg.gp.addmessage("Creating output folder: " + clccdir)
                        Cfg.gp.CreateFolder_management(Cfg.LCCBASEDIR,
                                                       path.basename(clccdir))
        #rows that were temporarily disabled
        rows = where(linkTable[:,Cfg.LTB_LINKTYPE]>100)
        linkTable[rows,Cfg.LTB_LINKTYPE] = (
            linkTable[rows,Cfg.LTB_LINKTYPE] - 100)
        # ---------------------------------------------------------------------

        # Create output geodatabase
        Cfg.gp.createfilegdb(Cfg.OUTPUTDIR, path.basename(Cfg.OUTPUTGDB))
        Cfg.gp.workspace = Cfg.OUTPUTGDB

        # Copy mosaic raster to output geodatabase
        mosRaster = "lcc_mos"
        count = 0
        statement = 'Cfg.gp.CopyRaster_management(mosaicRaster, mosRaster)'
        while True:
            try: exec statement
            except:
                count,tryAgain = lu.hiccup_test(count,statement)
                if not tryAgain: exec statement
            else: break

        Cfg.gp.pyramid = "PYRAMIDS 2"
        Cfg.gp.rasterStatistics = "STATISTICS 10 10"

        # ---------------------------------------------------------------------
        # convert mosaic raster to integer, set anything beyond Cfg.CWDTHRESH
        # to NODATA.
        truncRaster = "lcc_mosaic_meters_100000_max"
        expression = ("(" + mosaicRaster + " * (con(" + mosaicRaster + "<= " +
                      str(Cfg.CWDTHRESH) + ",1)))")
        count = 0
        statement = 'Cfg.gp.SingleOutputMapAlgebra_sa(expression, truncRaster)'
        while True:
            try: exec statement
            except:
                count,tryAgain = lu.hiccup_test(count,statement)
                if not tryAgain: exec statement
            else: break
        kmRaster = "lcc_mosaic_km_100_max"
        expression = "float(int((" + truncRaster + ") / 10)) / 100"
        count = 0
        statement = 'Cfg.gp.SingleOutputMapAlgebra_sa(expression, kmRaster)'
        while True:
            try: exec statement
            except:
                count,tryAgain = lu.hiccup_test(count,statement)
                if not tryAgain: exec statement
            else: break
        try:
            Cfg.gp.delete_management(truncRaster)
        except:
            pass
        # ---------------------------------------------------------------------


        startTime = time.clock()

        if Cfg.STEP4:
            finalLinkTable = lu.update_lcp_shapefile(linkTable, lastStep=4,
                                                     thisStep=5)
            startTime, hours, mins, secs = lu.elapsed_time(startTime)
        elif Cfg.STEP3:
            finalLinkTable = lu.update_lcp_shapefile(linkTable, lastStep=3,
                                                     thisStep=5)
            startTime, hours, mins, secs = lu.elapsed_time(startTime)
        else:
            # Don't know if step 4 was run, since this is started at step 5.
            # Will look for step 4 lcp file, then step 3.  FIXME: this is one
            # reason to remove old LCP files- or make a copy of step 3 with
            # step 4 filename.  Otherwise could retrieve a step 4 file when a
            # new run superceded it.
            finalLinkTable = lu.update_lcp_shapefile(linkTable, lastStep=4,
                                                     thisStep=5)
            startTime, hours, mins, secs = lu.elapsed_time(startTime)

        linkTableFile = lu.get_this_step_link_table(step=5)
        Cfg.gp.addmessage('\nUpdating ' + linkTableFile)
        lu.write_link_table(linkTable, linkTableFile)

        linkTableLogFile = path.join(Cfg.LOGDIR, "linkTable_STEP5.csv")
        lu.write_link_table(linkTable, linkTableLogFile)

        linkTableFinalFile = path.join(Cfg.OUTPUTDIR, "linkTable_Final.csv")
        lu.write_link_table(finalLinkTable, linkTableFinalFile)
        Cfg.gp.addmessage('Copy of final linkTable written to '+
                          linkTableFinalFile)

        # Pull out active corridor and constellation links
        numLinks=finalLinkTable.shape[0]
        rows, cols = where(
            finalLinkTable[:,Cfg.LTB_LINKTYPE:Cfg.LTB_LINKTYPE+1] ==
            Cfg.LT_CORR)
        coreLinks = finalLinkTable[rows,:]
        rows, cols = where(
            finalLinkTable[:,Cfg.LTB_LINKTYPE:Cfg.LTB_LINKTYPE+1] ==
            Cfg.LT_CLU)
        componentLinks = finalLinkTable[rows,:]
        activeLinkTable = append(coreLinks, componentLinks, axis=0)
        del componentLinks
        del coreLinks

        # sort by Cfg.LTB_LINKID
        ind = argsort((activeLinkTable[:,Cfg.LTB_LINKID]))
        activeLinkTable = activeLinkTable[ind]

        activeLinkTableFile = path.join(
            Cfg.OUTPUTDIR, "linkTable_Final_Active_Links_Only.csv")
        lu.write_link_table(activeLinkTable, activeLinkTableFile)
        Cfg.gp.addmessage('Table of active links written to ' +
                          activeLinkTableFile)

        lu.dashline()
        Cfg.gp.addmessage('\nCreating shapefiles with linework for links.')
        lu.write_link_maps(linkTableFile, step=5)

        # Create final linkmap files in output directory, and remove files from
        # scratch.
        lu.copy_final_link_maps()
        shutil.rmtree(Cfg.SCRATCHDIR)

    # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.dashline(1)
        Cfg.gp.addmessage('****Failed in step 5. Details follow.****')
        filename =  __file__
        lu.raise_geoproc_error(filename)

    # Return any PYTHON or system specific errors
    except:
        lu.dashline(1)
        Cfg.gp.addmessage('****Failed in step 5. Details follow.****')
        filename =  __file__
        lu.raise_python_error(filename)

    return