#!/usr/bin/env python2.6

"""Script to run Climate Corridor tool"""

import sys
import os.path as path


_SCRIPT_NAME = path.basename(__file__)


def main():
    """Runs Climate Corridor tool"""
    proj_dir = "W:\\demoProject"  # Project Directory

    # Core Inputs
    core_fc = "W:\\demoData\\cc_cores.shp"  # Core Feature Class
    core_fl = "HCA_ID"  # Core Identifer in Core Feature Class

    climate_rast = "W:\\demoData\\cc_climate.img"  # Climate Raster

    # Resistance Raster
    #resis_rast = "#"  # Can be run without resistance raster
    resis_rast = "W:\\demoData\\cc_resist.img"

    # GRASS GIS Folder
    #gisbase = "C:\\Program Files (x86)\\GRASS 6.4.2"
    #gisbase = "C:\\Program Files (x86)\\GRASS GIS 6.5.svn"
    gisbase = "C:\\Program Files (x86)\\GRASS GIS 7.0.svn"

    # Model Settings
    min_euc_dist = 2000  # Minimum Euclidean Distance
    max_euc_dist = 50000  # Maximum Euclidean Distance
    climate_threashold = 1  # Climate Threashold (e.g. degrees Celsius)
    climate_cost = 50000  # Climate Cost (e.g. 1 degree C change = 50km cost)

    prune_network = "False"
    max_nn = 4  # No of connected nearest neighbors
    nn_unit = "Cost-Weighted"  # NN Unit
    keep_constelations = "True"

    # Setup path and run model
    sys.path.append('..\\toolbox\\scripts')
    import cc_main

    argv = (_SCRIPT_NAME, proj_dir, core_fc, core_fl, climate_rast, resis_rast,
            gisbase, min_euc_dist, max_euc_dist, climate_threashold,
            climate_cost, prune_network, max_nn, nn_unit, keep_constelations)

    cc_main.main(argv)


if __name__ == "__main__":
    main()
