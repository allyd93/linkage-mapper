#!/usr/bin/env python2.5

"""Master script for barrier analysis in linkage mapper.

Reguired Software:
ArcGIS 9.3 with Spatial Analyst extension
Python 2.5
Numpy

"""

import os.path as path
import arcgisscripting
from lm_config import Config as Cfg
import lm_util as lu
import s6_barriers as s6 

import arcpy

_filename = path.basename(__file__)

if not Cfg.LOGMESSAGES:
    gprint = arcpy.AddMessage
else:
    gprint = lu.gprint


def bar_master():
    """ Experimental code to detect barriers using cost-weighted distance
    outputs from Linkage Mapper tool.
    
    """
    try:
        lu.create_dir(Cfg.LOGDIR)
        lu.create_dir(Cfg.MESSAGEDIR)

        Cfg.logFile=lu.create_log_file(Cfg.MESSAGEDIR, Cfg.TOOL, Cfg.PARAMS)
                
        # Move adj and cwd results from earlier versions to datapass directory
        lu.move_old_results()
        
        # Delete final ouptut geodatabase
        lu.delete_dir(Cfg.BARRIERGDB)
        if not arcpy.Exists(Cfg.BARRIERGDB):
            # Create output geodatabase
            arcpy.CreateFileGDB_management(Cfg.OUTPUTDIR, path.basename(Cfg.BARRIERGDB))        
                
        lu.create_dir(Cfg.OUTPUTDIR)
        lu.delete_dir(Cfg.SCRATCHDIR)
        lu.create_dir(Cfg.SCRATCHDIR) 
        lu.create_dir(Cfg.ARCSCRATCHDIR)
        
        arcpy.env.extent = Cfg.RESRAST_IN
        arcpy.env.snapRaster = Cfg.RESRAST_IN

        gprint('\nMaking local copy of resistance raster.')
        lu.delete_data(Cfg.RESRAST)
        arcpy.CopyRaster_management(Cfg.RESRAST_IN, Cfg.RESRAST)          
     
        s6.STEP6_calc_barriers()
        
        #clean up
        lu.delete_dir(Cfg.SCRATCHDIR)
        if Cfg.SAVEBARRIERDIR ==  False:
            lu.delete_dir(Cfg.BARRIERBASEDIR)
        gprint('\nDONE!\n')


    # Return GEOPROCESSING specific errors
    except arcgisscripting.ExecuteError:
        lu.exit_with_geoproc_error(_filename)

    # Return any PYTHON or system specific errors
    except:
        lu.exit_with_python_error(_filename)

if __name__ == "__main__":
    bar_master()

    
    
        # desc = arcpy.Describe(Cfg.RESRAST_IN)

        # if hasattr(desc, "name"):
            # gprint ("Name:        " + desc.name)

        # if hasattr(desc, "catalogPath"):
            # gprint ("CatalogPath: " + desc.catalogPath)
    