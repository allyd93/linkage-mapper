#!/usr/bin/env python2.5
# Authors: Brad McRae and Darren Kavanagh

""" Step 1: Get adjacencies.

Determines adjacencies between core areas in either or both Euclidean and
cost-weighted distance space

"""

__filename__ = "s1_getAdjacencies.py"
__version__ = "0.7.5"

import shutil
import time
import os.path as path

import numpy as npy

import arcgisscripting

from lm_config import Config as Cfg
import lm_util as lu

gp = Cfg.gp
gprint = gp.addmessage

BNDCIRCENWD = path.join(Cfg.SCRATCHDIR, Cfg.BNDCIRCEN)
BNDCIRWD = path.join(Cfg.SCRATCHDIR, Cfg.BNDCIR)
EUC_BNDCIRCEN = "euc" + Cfg.BNDCIRCEN
EUC_BNDCIRCENWD = path.join(Cfg.SCRATCHDIR, EUC_BNDCIRCEN)
EUC_BNDCIR = "euc" + Cfg.BNDCIR
EUC_BNDCIRWD = path.join(Cfg.SCRATCHDIR, EUC_BNDCIR)
S1CORE_RAS = "s1core_ras"


def STEP1_get_adjacencies():
    """Determines adjacencies between core areas in either or both
    Euclidean and cost-weighted distance space.

    """
    try:
        lu.dashline(1)
        gprint('Running script ' + __filename__)        

        # Default behavior is to use same cell size as resistance raster,
        # but this can be changed here.
        gp.scratchWorkspace = Cfg.SCRATCHDIR
        gp.workspace = Cfg.PROJECTDIR

        gprint('Adjacency files will be written to ' +
                          Cfg.ADJACENCYDIR)

        #remove adj directory
        lu.delete_dir(Cfg.ADJACENCYDIR)                        
            
        gp.CreateFolder_management(path.dirname(Cfg.ADJACENCYDIR),
                                       path.basename(Cfg.ADJACENCYDIR))
 
        # ------------------------------------------------------------------
        # Create bounding circles to limit cwd and allocation calculations
        if Cfg.BUFFERDIST is not None:
            gprint('Reducing processing area using bounding circle '
                              'plus buffer of ' +
                              str(float(Cfg.BUFFERDIST)) + ' map units')

            gp.MakeFeatureLayer(Cfg.COREFC, Cfg.FCORES)

            extentBoxList = npy.zeros((0, 5), dtype='float32')
            boxCoords = lu.get_extent_box_coords()
            extentBoxList = npy.append(extentBoxList, boxCoords, axis=0)
            extentBoxList[0, 0] = 0

            # cwd bounding circle- used to clip raster to limit cwd
            # calculations
            boundingCirclePointArray = npy.zeros((0, 5), dtype='float32')
            circlePointData = lu.get_bounding_circle_data(extentBoxList, 0, 0,
                                                          Cfg.BUFFERDIST)
            lu.make_points(Cfg.SCRATCHDIR, circlePointData, Cfg.BNDCIRCEN)            
            
            lu.delete_data(BNDCIRWD)
            gp.buffer_analysis(path.join(Cfg.SCRATCHDIR, Cfg.BNDCIRCEN),
                                             BNDCIRWD, "radius")
            # boundingCirclePointArray  = npy.zeros((0, 5),dtype='float32')
            # circlePointData = lu.get_bounding_circle_data(extentBoxList, 0,
            #                                               0, Cfg.BUFFERDIST)

            # euc bounding circle- at the moment just limits extent of
            # euclidean allocation calculations
            boundingCirclePointArray = npy.zeros((0, 5), dtype='float32')
            # no buffer needed
            circlePointData = lu.get_bounding_circle_data(
                extentBoxList, 0, 0, 0)
            lu.make_points(Cfg.SCRATCHDIR, circlePointData, EUC_BNDCIRCEN)
            lu.delete_data(EUC_BNDCIRWD)
            gp.buffer_analysis(EUC_BNDCIRCENWD, EUC_BNDCIRWD, "radius")

            del boundingCirclePointArray

        gp.pyramid = "NONE"
        gp.rasterstatistics = "NONE"
        gp.workspace = Cfg.SCRATCHDIR

        if Cfg.S1ADJMETH_CW:
            cwadjacency()
        if Cfg.S1ADJMETH_EU:
            euadjacency()
        
            
        # Clean up
        lu.delete_data(S1CORE_RAS)
            

    # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')
        lu.raise_geoproc_error(__filename__)

    # Return any PYTHON or system specific errors
    except:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')
        lu.raise_python_error(__filename__)
    return


def cwadjacency():
    """Calculate cost-weighted adjacency

       Inputs: gp - geoprocessing object

    """
    try:
        alloc_rasFN = "Cwd_alloc_ras"
        gprint('\nCalculating cost-weighted distance adjacency')
        outcsvfile = path.join(Cfg.DATAPASSDIR, "cwdAdj.csv")
        outcsvLogfile = path.join(Cfg.LOGDIR, "cwdAdj_STEP1.csv")
        PREFIX = Cfg.PREFIX
        
        # May need to set extent prior to core poly to raster conversion...
        # ----------------------------------------------
        # Cost-weighted allocation code
        if Cfg.BUFFERDIST is not None:
            # Clip resistance raster using bounding circle
            start_time = time.clock()
            bResistance = path.join(Cfg.SCRATCHDIR, "bResistance")
            gp.ExtractByMask_sa(Cfg.RESRAST, BNDCIRWD,
                                    bResistance)
            gprint('\nReduced resistance raster extracted using '
                              'bounding circle.')
            start_time = lu.elapsed_time(start_time)
        else:
            bResistance = Cfg.RESRAST

        start_time = time.clock()
        gprint('Starting cost weighted distance allocation...')

        # core_rastmp = 'core_rastmp'
        if Cfg.TMAXCWDIST is not None:
            gprint('Maximum cost-weighted distance set to ' +
                              str(Cfg.TMAXCWDIST))
        gp.CellSize = gp.Describe(bResistance).MeanCellHeight
        gp.extent = "MAXOF"
        gprint('Processing cell size: ' + gp.CellSize)
        count = 0
        statement = ('gp.FeatureToRaster_conversion(Cfg.COREFC, '
                     'Cfg.COREFN, S1CORE_RAS, gp.Cellsize)')
        while True:
            try:
                exec statement
            except:
                count, tryAgain = lu.hiccup_test(count, statement)
                if not tryAgain:
                    exec statement
            else:
                break

        #Convert core raster to integer format Not implemented.
        # if gp.exists(S1CORE_RAS):
            # gp.delete_management(S1CORE_RAS)           
        # gp.Int_sa(core_rastmp, S1CORE_RAS)
        # gp.delete_management(core_rastmp)
        
                
        gp.workspace = Cfg.ADJACENCYDIR
        gp.scratchworkspace = gp.workspace
        
        if not gp.exists(Cfg.CWDGDB):
            gp.createfilegdb(Cfg.OUTPUTDIR, path.basename(Cfg.CWDGDB))
        outDistanceRaster = path.join(Cfg.CWDGDB, PREFIX + "_cwd")
        alloc_ras = path.join(Cfg.ADJACENCYDIR, alloc_rasFN)
        s1core_ras_path = path.join(Cfg.SCRATCHDIR, S1CORE_RAS)
        count = 0
        statement = ('gp.Costallocation_sa(s1core_ras_path, bResistance, '
                     'alloc_ras, Cfg.TMAXCWDIST, s1core_ras_path, "VALUE", '
                     'outDistanceRaster, "")')
        while True:
            try:
                exec statement
            except:
                count, tryAgain = lu.hiccup_test(count, statement)
                if not tryAgain:
                    exec statement
            else:
                break

        gp.scratchworkspace = Cfg.SCRATCHDIR
        gprint('\nCost-weighted distance allocation done.')
        start_time = lu.elapsed_time(start_time)
        adjshiftwrite(alloc_ras, outcsvfile, outcsvLogfile)

        
        # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')
        lu.raise_python_error(__filename__)

    # Return any PYTHON or system specific errors
    except:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')
        lu.raise_python_error(__filename__)


def euadjacency():
    """Calculate Euclidean adjacency

       Inputs: gp - geoprocessing object

    """
    try:
        alloc_rasFN = "Euc_alloc_ras"
        lu.dashline()
        gprint('Calculating Euclidean adjacency')
        outcsvfile = path.join(Cfg.DATAPASSDIR, "eucAdj.csv")
        outcsvLogfile = path.join(Cfg.LOGDIR, "eucAdj_STEP1.csv")

        # ----------------------------------------------
        # Euclidean allocation code
        gp.workspace = Cfg.ADJACENCYDIR
        gprint('Starting Euclidean adjacency processing...')
        # Euclidean cell size
        cellSizeEuclidean = gp.Describe(Cfg.RESRAST).MeanCellHeight
        # gprint('Euclidean cell size set equal to resistance '
                      # 'raster cell size (' +
                      # str(cellSizeEuclidean) + ').')

        # core_rastmp = 'core_rastmp'
        oldextent = gp.extent
        if Cfg.BUFFERDIST is not None:
            gp.extent = gp.Describe(BNDCIRWD).extent
        count = 0
        statement = ('gp.FeatureToRaster_conversion(Cfg.COREFC, '
                     'Cfg.COREFN, S1CORE_RAS, cellSizeEuclidean)')
        while True:
            try:
                exec statement
            except:
                count, tryAgain = lu.hiccup_test(count, statement)
                if not tryAgain:
                    exec statement
            else:
                break

        start_time = time.clock()

        gp.scratchworkspace = gp.workspace
        outDistanceRaster = path.join(Cfg.ADJACENCYDIR, "euc")
        alloc_ras = path.join(Cfg.ADJACENCYDIR, alloc_rasFN)
        count = 0
        statement = ('gp.EucAllocation_sa(S1CORE_RAS, alloc_ras, "","", '
                     'cellSizeEuclidean, "", outDistanceRaster, "")')
        while True:
            try:
                exec statement
            except:
                count, tryAgain = lu.hiccup_test(count, statement)
                if not tryAgain:
                    exec statement
            else:
                break

        gp.scratchworkspace = Cfg.SCRATCHDIR
        gprint('\nEuclidean distance allocation done.')
        start_time = lu.elapsed_time(start_time)
        gp.extent = oldextent
        adjshiftwrite(alloc_ras, outcsvfile, outcsvLogfile)

        # Clean up
        lu.delete_data(outDistanceRaster)

    
     # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')

        lu.raise_geoproc_error(__filename__)

    # Return any PYTHON or system specific errors
    except:
        lu.dashline(1)
        gprint('****Failed in step 1. Details follow.****')

        lu.raise_python_error(__filename__)


def adjshiftwrite(araster, csvfile, logfile):
    """Get adjacencies using shift method and write to disk"""
    # To be replaced by getLeastCostDistsUsingShiftMethod if implemented
    adjTable = lu.get_adj_using_shift_method(araster)
    lu.write_adj_file(csvfile, adjTable)
    lu.write_adj_file(logfile, adjTable)
