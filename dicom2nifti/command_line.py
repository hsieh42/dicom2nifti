#!/usr/bin/env python
__author__ = 'HsiehM'
__EXEC__ = 'SortAndRenameDicoms'

import sys
import os
import traceback as tb 
import logging as _log
import argparse
from distutils.spawn import find_executable 

try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(_log.Handler):
        def emit(self, record):
            pass

_log.getLogger().addHandler(NullHandler())

def main(argv = None):
    # check dcm2nii executable  
    cmd = find_executable('dcm2nii')
    if not cmd:
        raise OSError('dcm2nii command cannot be found in system path.')
        
    if argv is None:
        argv = sys.argv[1:]
        
    # parse input from command line
    args = create_parser().parse_args(argv)
     
    import socket, time

    exe_folder = os.getcwd()
    exe_time = time.strftime("%Y-%m-%d %a %H:%M:%S", time.localtime())
    host = socket.gethostname()
    print "Command", __EXEC__
    print "Arguments", args
    print "Executing on", host
    print "Executing at", exe_time
    print "Executing in", exe_folder
    
    # start doing stuff
    import dicom2nifti as dcmnii
    #print 'test logging'
    log_level = _log.WARNING
    if args.verbosity == 2:
        log_level = _log.DEBUG
    elif args.verbosity == 1:
        log_level = _log.INFO
    
    logger = _log.getLogger()       
    logger.setLevel(log_level)

    try:
        dcmnii.convert_one_directory(args.input_dir, args.output_dir, tmp_dir = args.tmpdir,
                                     log = args.log, keyword = args.keyword, exclude = args.exclude,
                                     recursive = True, orientation = args.orientation, mode = args.mode,
                                     group_by = args.group_by, force = args.force)
    except:
        print 'Failed at converting ', args.input_dir
        tb.print_exception(sys.exc_info()[0], sys.exc_info()[1], sys.exc_info()[2])
        raise
        
    return 0        
        

def create_parser():
    ''' Create an argparse.ArgumentParser object 
    
        :returns: An argparse.ArgumentParser parser.
    '''
    parser = argparse.ArgumentParser(prog = __EXEC__,
                                     description = 'Sort, rename, and convert dicoms to Nifti.')
    # Required
    parser.add_argument('-i', '--inputdir',
                        required = True,
                        dest = 'input_dir',
                        action = 'store',
                        type = str,
                        help = 'Dicom directory to be sorted')
    parser.add_argument('-o', '--outputDir', '--outputdir',
                        required = True,
                        dest = 'output_dir',
                        action = 'store',
                        type = str,
                        help = 'The output directory to save dicoms and Nifti')

    ## optional
    parser.add_argument('-l', '--log',
                        dest = 'log',
                        action = 'store',
                        default = None,
                        type = str,
                        help = 'Specify a log filename. If the log is already present, only new dicoms will be processed. If log option is not presented, log will not be generated, also all dicoms found in input directory will be converted which may overwrite the existing files in output directory.')
    parser.add_argument('-g', '--groupby',
                        dest = 'group_by',
                        action = 'store',
                        default = ['SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription'],
                        type = str,
                        nargs='+',
                        help = 'Group dicoms by the dicom tag names (case-sensitive). Default: SeriesInstanceUID, SeriesNumber, SeriesDescription.')
    parser.add_argument('-E', '--exclude',
                        dest = 'exclude',
                        action = 'store',
                        default = ['localizer', 'moco'],
                        type = str,
                        nargs='+',
                        help = 'Do NOT convert series containing this string (case-insensitive)')
    parser.add_argument('-e', '--exclusive',
                        dest = 'keyword',
                        action = 'store',
                        type = str,
                        nargs='+',                        
                        help = 'Only convert series containing these string (case-insensitive)')
    parser.add_argument('-r', '--orient',
                        dest = 'orientation',
                        action = 'store',
                        default = 'LPS',
                        type = str,
                        help = 'The orientation of the nifti files in to convention, ex. LPS: Right-Left, Anterior-Posterior, Inferior-Superior.')
    parser.add_argument('-m', '--mode',
                        dest = 'mode',
                        action = 'store',
                        default = 'symbolic',
                        choices = ['symbolic', 'move', 'copy', 'skip'],
                        type = str,
                        help = 'There are four ways to deal with sorted dicoms. "symbolic": create soft/symbolic links at output_dir. (overwrite existing links); "copy": create a new copy of files in output_dir; "move": rename the original dicoms and move to output_dir. Creating symbolic link is highly recommended to reduce filesystem IO during runtime and also to preserve the linkage between unsorted files to sorted files; alternatively, "skip" allows user to skip the creation of sorted dicoms which is useful when one just wants to get the converted Nifti images.')
    parser.add_argument('-v', '--verbose',
                        dest = 'verbosity',
                        action = 'count',
                        help = 'Increase verbosity of the program. By calling the flag multiple time, the verbosity can be further increased. Max: 2 levels (-v -v)')
    parser.add_argument('-w', '--workingDir',
                        dest = 'tmpdir',
                        action = 'store',
                        type = str,
                        help = 'A temporary working directory to save intermediate files')
    parser.add_argument('-f', '--force',
                        dest = 'force',
                        action = 'store_true',
                        default = False,
                        help = 'Force sorting and converting even if the sequence exists in the log file and overwrite.')
#    parser.add_argument('-R', '--recursive',
#                        dest = 'recursive',
#                        action = 'store_true',
#                        default = False,
#                        help = 'Force sorting and converting even if the sequence exists in the log file and overwrite.')
    return parser
                                  
                        
if __name__ == '__main__':
    sys.exit(main())
