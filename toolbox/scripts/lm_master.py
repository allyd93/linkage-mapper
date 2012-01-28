#!/usr/bin/env python2.5
# Authors: Brad McRae and Darren Kavanagh

"""Master script for Linkage Lapper.

Reguired Software:
ArcGIS 9.3 with Spatial Analyst extension
Python 2.5
Numpy

"""

__filename__ = "lm_master.py"
__version__ = "0.7.7beta"

import os.path as path
import os

import arcgisscripting

import numpy as npy
from lm_config import Config as Cfg
import lm_util as lu
import s1_getAdjacencies as s1
import s2_buildNetwork as s2
import s3_calcCwds as s3
import s4_refineNetwork as s4
import s5_calcLccs as s5

gp = Cfg.gp

if not Cfg.LOGMESSAGES:
    gprint = gp.addmessage
else:
    gprint = lu.gprint


def lm_master():
    """Main function for linkage mapper.

    Called by ArcMap with parameters or run from command line with parameters
    entered in script below.  Calls functions in dedicated scripts for each of
    5 processing steps.

    """
    try:

        # Move results from earlier versions to new directory structure
        lu.move_old_results()
        
        # Create output directories if they don't exist
        if gp.Exists(Cfg.OUTPUTDIR):
            gp.RefreshCatalog(Cfg.OUTPUTDIR)
        lu.createfolder(Cfg.OUTPUTDIR)
        lu.createfolder(Cfg.LOGDIR)
        lu.createfolder(Cfg.MESSAGEDIR)
        lu.createfolder(Cfg.DATAPASSDIR)
        # Create fresh scratch directory
        lu.delete_dir(Cfg.SCRATCHDIR)
        lu.createfolder(Cfg.SCRATCHDIR)
        
        Cfg.logFile=lu.create_log_file(Cfg.MESSAGEDIR, Cfg.TOOL, Cfg.PARAMS)
        
        installD = gp.GetInstallInfo("desktop")        
        gprint('\nLinkage Mapper Version ' + str(__version__))
        try:
            gprint('on ArcGIS '+ installD['ProductName'] + ' ' + 
                installD['Version'] + ' Service Pack ' + installD['SPNumber'])
        except: pass    
                
        # Check core ID field.
        lu.check_cores(Cfg.COREFC, Cfg.COREFN) 
                        
        # Identify first step cleanup link tables from that point
        lu.dashline(1)
        if Cfg.STEP1:
            gprint('Starting at step 1.')       
            firststep = 1
        elif Cfg.STEP2:
            gprint('Starting at step 2.')
            firststep = 2
        elif Cfg.STEP3:
            gprint('Starting at step 3.')
            firststep = 3
            linkTableFile = lu.get_prev_step_link_table(step=3)  # Check exists
        elif Cfg.STEP4:
            gprint('Starting at step 4.')
            firststep = 4
            linkTableFile = lu.get_prev_step_link_table(step=4)  # Check exists
        elif Cfg.STEP5:
            gprint('Starting at step 5.')
            firststep = 5
            linkTableFile = lu.get_prev_step_link_table(step=5)  # Check exists
        lu.clean_up_link_tables(firststep)

        gp.OverwriteOutput = True
        
        
        # Make a local grid copy of resistance raster for cwd runs-
        # will run faster than gdb.
        # Don't know if raster is in a gdb if entered from TOC
        lu.delete_data(Cfg.RESRAST)
        gp.pyramid = "NONE"
        gp.rasterstatistics = "NONE"
        
        gprint('\nMaking temporary copy of resistance raster for this run.')
        gp.Extent = gp.Describe(Cfg.RESRAST_IN).Extent        
        gp.SnapRaster = Cfg.RESRAST_IN
        gp.CopyRaster_management(Cfg.RESRAST_IN, Cfg.RESRAST)  

        # gp.Extent = gp.Describe(Cfg.RESRAST).Extent        
        # gp.SnapRaster = Cfg.RESRAST

        if (Cfg.STEP1) or (Cfg.STEP3):
            # Make core raster file
            gprint('\nMaking temporary raster of core file for this run.')
            gp.FeatureToRaster_conversion(Cfg.COREFC, Cfg.COREFN, 
                          Cfg.CORERAS, gp.Describe(Cfg.RESRAST).MeanCellHeight)        
         # #   gp.RasterToPolygon_conversion(Cfg.CORERAS, Cfg.COREFC, 
                                              # "NO_SIMPLIFY")                

        def delete_final_gdb(finalgdb):
            if gp.Exists(finalgdb) and Cfg.STEP5:
                try:
                    lu.clean_out_workspace(finalgdb)

                except:
                    lu.dashline(1)
                    msg = ('ERROR: Could not remove contents of geodatabase ' +
                           finalgdb + '. Is it open in ArcMap?\n You may '
                           'need to re-start ArcMap to release the file lock.')
                    lu.raise_error(msg)
                    
        # Delete final output geodatabase
        delete_final_gdb(Cfg.OUTPUTGDB_OLD)
        delete_final_gdb(Cfg.OUTPUTGDB)
        delete_final_gdb(Cfg.EXTRAGDB)
        delete_final_gdb(Cfg.LINKMAPGDB) 

        gp.OutputCoordinateSystem = gp.describe(Cfg.COREFC).SpatialReference                                              
        # Run linkage mapper processing steps
        if Cfg.STEP1:
            s1.STEP1_get_adjacencies()
        if Cfg.STEP2:
            s2.STEP2_build_network()
        if Cfg.STEP3:
            s3.STEP3_calc_cwds()
        if Cfg.STEP4:
            s4.STEP4_refine_network()
        if Cfg.STEP5:
            s5.STEP5_calc_lccs()
        
        # Clean up
        lu.delete_dir(Cfg.SCRATCHDIR)
        lu.close_log_file()
        
        gp.addmessage('\nDONE!\n')
        
        # severity = gp.MaxSeverity
        # gprint(str(severity))
        # test=gp.GetMessages(2)
        # if severity>1: 
            # gprint('Linkage Mapper SUCCEEDED. You can ignore any failure '
                    # 'messages from ArcGIS below.')

        return 
    # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.raise_geoproc_error(__filename__)

    # Return any PYTHON or system specific errors
    except:
        lu.raise_python_error(__filename__)

if __name__ == "__main__":
    lm_master()
