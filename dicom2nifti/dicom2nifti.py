#!/usr/bin/env python
__author__ = 'HsiehM'

import os as _os
import sys as _sys
import shutil as _shutil    
import traceback as _tb
import logging as _log
import tempfile as _tmp
import uuid as _uuid
from distutils.spawn import find_executable as _find_executable

#from memory_profiler import profile

# import external modules and make them available to users
#_sys.path.append('/cbica/home/hsiehm/Scripts/python_collections/lib/python2.7/site-packages/dcmstack-0.6_cbica_edit-py2.7.egg')
import dcmstack
import nibabel as nib
import dicom

# create system logger
_module_logger = _log.getLogger(__name__)
_ch = _log.StreamHandler()
_formatter = _log.Formatter(fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s',
                            datefmt = '%Y%m%d-%H:%M:%S')
_ch.setFormatter(_formatter)
_module_logger.addHandler(_ch)    

def is_dicom( dcmpath ):
    ''' Return True if the input file is a valid dicom that can be read by :func:`dicom.read_file`.

        :param dcmpath:  A filepath.
        :type dcmpath: str
        :returns:  True if dcmpath is a dicom image.
    '''
    _module_logger.debug('received a call to is_dicom')
    try:
        dicom.read_file(dcmpath, stop_before_pixels=True)
        return True
    except dicom.errors.InvalidDicomError:
        _module_logger.error(dcmpath + ' is not a valid dicom.')
        return False
    except Exception, e:
        _module_logger.error('Unknown error occurred: ' + _sys.exc_info()[0] + str(e))
        return False
    
def is_enhanced( dcm_ds ):
    ''' Return True if the input :class:`dicom.dataset.FileDataset` is of Enhanced format by checking
        (0002,0002) field in the meta file.
        Enhanced format has UID: 1.2.840.10008.5.1.4.1.1.4.1

        :param dcm_ds:  Input dicom to check the type.
        :type dcm_ds: dicom.dataset.FileDataset
        :returns:  True if dcm_ds is of enhanced format or False if not.
    '''
    _module_logger.debug('received a call to is_enhanced')
    if dcm_ds.file_meta.has_key(dicom.tag.Tag((0x0002,0x0002))):
        if dcm_ds.file_meta[0002,0002].value == '1.2.840.10008.5.1.4.1.1.4.1':
            return True

    return False

# commented part are very expensive operations
def discover_files( input_dir, recursive = False ):
    ''' Return a list of files found in a given directory.
    
        :param input_dir: An input directory to discover dicom files.
        :type input_dir: str
        :param recursive: A switch to perform the operation recursively. It might be time-consuming.
        :type recursive: boolean
        :returns: A list of files found in input_dir.
    '''
    _module_logger.debug('received a call to discover_files')    
    input_dir = _os.path.abspath( input_dir )
    if recursive:
        src_files = []
        for dirpath, dirnames, filenames in _os.walk(input_dir):
            # ignore hidden files and directories
            filenames = [f for f in filenames if not f[0] == '.']
            dirnames[:] = [d for d in dirnames if not d[0] == '.']
            for filename in filenames:
                filepath = _os.path.join(dirpath, filename)
                src_files.append(filepath)
#                if filepath.endswith('dcm'): ## tmp TODO remove
#                    src_files.append(filepath) ## tmp TODO dedent
    else:
        from glob import glob as _glob
        src_files = _glob( _os.path.join(input_dir, '*') )

    return src_files
    
def can_parse_and_group( src_dcms ):
    ''' Return True if the input list of files can be parsed and grouped as dicoms, False otherwise.
    
        :param src_dcms:  A list of dicom filenames.
        :type src_dcms: list
        :returns: Boolean.
    '''
    _module_logger.debug('received a call to can_parse_and_group')     
    try:
        dcmstack.parse_and_group(src_dcms)
        return True
    except IOError:
        _module_logger.error("Cannot read the input dicom series.")
    except MemoryError:
        _module_logger.error("Not enough memory to read the input dicom series.")
    except Exception, e:
        _module_logger.error("Unexpected error:" + _sys.exc_info()[0] + str(e))
    return False

def get_all_dicom_groups( src_dcms, group_by = ['SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription']):
    ''' Return a dict that the keys being sequence information and values being list of dicoms of 
        that sequence from a list of dicoms. The output dicoms will be sorted by dicom tag InstanceNumber.

        :param src_dcms:  A list of dicom filenames.
        :type src_dcms: list
        :returns:  A dict mapping tuples of values (corresponding to 'group_by') to groups of data sets parsed by :func:`dcmstack.parse_and_group`. Each element in the list is a tuple
        containing the dicom object, the parsed meta data, and the filename.
    '''
    _module_logger.debug('received a call to get_all_dicom_groups')     
    dcm_groups = dcmstack.parse_and_group(src_dcms, warn_on_except = True, force = False,
                                          group_by = group_by)

    for key, dcm_dataset in dcm_groups.iteritems():
        has_instance_number = all([ True for i in xrange(len(dcm_dataset))
                                         if 'InstanceNumber' in dcm_dataset[i][1] ])
        if has_instance_number:
            dcm_groups[key] = sorted(dcm_dataset, key=lambda x:x[1].get('InstanceNumber'))

    return dcm_groups


## TODO 20180411 It would not distinguish sequence from different date with identical Series descriptions and series numbers
def get_all_dicoms_from_sequences( dcm_groups, keyword = None, exclude = None):
    ''' Return a list of dicom filepaths from a input dcm_groups. Keyword/Exclude can be used to
        select/filter the sequence of interest.
        With this function, choose the sequence of interest and call :func:`dicom2nifti.convert_one_sequence`

        :param dcm_groups:  A dict mapping tuples of values (corresponding to 'group_by') to
                            groups of data sets parsed by :func:`dcmstack.parse_and_group`. Each element
                            in the list is a tuple containing the dicom object, the parsed meta
                            data, and the filename.
        :type dcm_groups: dict
        :param keyword:  A list of search string for specific sequence in a dcm_groups. Ex. ['T1', 'DWI'].
        :type keyword: str or list of strings
        :param exclude:  A list of search string for excluding specific sequence in a dcm_groups. Ex. ['localizer', 'MoCoSeries'].
        :type exclude: str or list of strings
        :returns:  A dict of sequence information as keys and list of selected dicom filenames as values.
    '''
    _module_logger.debug('received a call to get_all_dicoms_from_sequences')   
    if isinstance(keyword, str):
        keyword = [keyword]
    if isinstance(exclude, str):
        exclude = [exclude]

    # TODO 20160816 Michael Hsieh: same sequence from multiple studies would be overwritten cos UID (key[0]) is omitted.
    # keyword provided while exclude is empty
    if keyword and keyword is not None and exclude is None:
        out_dcm_groups = { key: [i[2] for i in dcm_groups[key]]
                           for key in dcm_groups.keys() if isinstance(key[-1], (str, unicode))
                           for kw in keyword if kw.upper() in key[-1].upper() }
                           
    elif exclude and exclude is not None:
        dummy_dcm_groups = dcm_groups.copy()
        for key in dummy_dcm_groups.keys():
            if isinstance(key[-1], (str, unicode)):
                for ex in exclude:
                    if ex.upper() in key[-1].upper():
                        dummy_dcm_groups.pop(key)
        if keyword is None:
            out_dcm_groups = { key: [i[2] for i in dummy_dcm_groups[key]]
                               for key in dummy_dcm_groups.keys() if isinstance(key[-1], (str, unicode))  }
        else:
            out_dcm_groups = { key: [i[2] for i in dummy_dcm_groups[key]]
                           for key in dummy_dcm_groups.keys() if isinstance(key[-1], (str, unicode))
                           for kw in keyword if kw.upper() in key[-1].upper() }
        dummy_dcm_groups = None
    else:
        out_dcm_groups = { key: [i[2] for i in dcm_groups[key]]
                           for key in dcm_groups.keys() if isinstance(key[-1], (str, unicode)) }
        
    return out_dcm_groups

def get_dataset_id( dcm_meta ):
    ''' Return an subject identifier from the dicom header in an input meta file.
        Search order: PatientID [0x0010,0x0020], StudyID [0x0020, 0x0010],
        AccessionNumber [0x0008, 0x0050]

        :param dcm_meta: dicom header information.
        :type dcm_meta: dicom.dataset.FileDataset or OrderedDict
        :returns:  a subject identifier in string.
    '''
    _module_logger.debug('received a call to get_dataset_id')
    if 'PatientID' in dcm_meta:
        dataset_id = dcm_meta.get('PatientID')
    elif 'StudyID' in dcm_meta:
        dataset_id = dcm_meta.get('StudyID')
    elif 'AccessionNumber' in dcm_meta:
        dataset_id = dcm_meta.get('AccessionNumber')
    else:
        raise KeyError('Cannot find fields containing dataset identifier in the meta information.')
    
    if dataset_id is None:
        raise ValueError('''Cannot find ID from all three possible fields:
                            PatientID, StudyID, and AccessionNumber. ''')
    else:
        return dataset_id.replace(' ', '_').replace('$', '').replace(':', '.')

def get_dataset_date( dcm_meta ):
    ''' Return an subject imaging date from the dicom header in an input meta file.
        Search order: AcquisitionDate [0x0008, 0x0022], StudyDate [0x0008, 0x0020].

        :param dcm_meta: dicom header information.
        :type dcm_meta: dicom.dataset.FileDataset or OrderedDict
        :returns:  a date in string.
    '''
    _module_logger.debug('received a call to get_dataset_date')    
    if 'AcquisitionDate' in dcm_meta:
        dataset_date = dcm_meta.get('AcquisitionDate')
    elif 'StudyDate' in dcm_meta:
        dataset_date = dcm_meta.get('StudyDate')
    else:
        raise KeyError('Cannot find fields containing dataset timestamp in the meta information.')
    
    if dataset_date is None:
        raise ValueError('''Cannot find ID from all two possible fields:
                            AcquisitionDate, and StudyDate. ''')
    else:
        return dataset_date

def get_sequence_info( dcm_meta ):
    ''' Return a sequnce information in CBICA convention from the dicom header in
        an input meta file.

        :param dcm_meta: dicom header information.
        :type dcm_meta: dicom.dataset.FileDataset or OrderedDict
        :returns:  A CBICA sequence information (<SeriesDescription>-<SeriesNumber>) in string.
    '''
    _module_logger.debug('received a call to get_sequence_info')    
    sequence_info = ''
    if 'SeriesDescription' in dcm_meta:
        sequence_info = dcm_meta.get('SeriesDescription')
    elif 'ProtocolName' in dcm_meta:
        sequence_info = dcm_meta.get('ProtocolName')
    elif 'SequenceName' in dcm_meta:
        sequence_info = dcm_meta.get('SequenceName')
    else:
        raise KeyError('Cannot find fields containing sequence in the meta information from SeriesDescription, ProtocolName or SequenceName.')

    if 'SeriesNumber' in dcm_meta:
        sequence_number = dcm_meta.get('SeriesNumber')
        sequence_info = '%s-%s' % (sequence_info, sequence_number)

    if not sequence_info:
        raise ValueError('''Cannot determine Sequence infotmation from two fields:
                            SeriesDescription, and SeriesNumber. ''')
    else:
        return sequence_info.replace(' ', '_').replace('/','_').replace('(','').replace(')','').replace('*', '').replace('&', '').replace('$', '').replace(':', '.')

def get_subject_id( dcm_meta ):
    ''' Return an subject identifier in CBICA convention from the dicom header in
        an input meta file.

        :param dcm_meta: dicom header information.
        :type dcm_meta: dicom.dataset.FileDataset or OrderedDict
        :returns:  A CBICA subject identifier (<PatientID>-<AcquisitionDate>) in string. 
    '''
    _module_logger.debug('received a call to get_subject_id')    
    ID = get_dataset_id(dcm_meta)
    DATE = get_dataset_date(dcm_meta)
    return '%s-%s' % (ID, DATE)

def organize_one_sequence( dicom_files, output_dir, prefix = None, mode = 'symbolic' ):
    ''' Organize the input dicom_files to standardized and readable filenames. Return a list 
        of sorted filenames.
         
        There are three ways to create sorted filenames:
        
        - symbolic: create soft/symbolic links at output_dir. (overwrite existing links)
        - copy: create a new copy of files in output_dir.
        - move: rename the original dicoms and move to output_dir
        
        Creating symbolic link is highly recommended to reduce filesystem IO during runtime 
        and also to preserve the linkage between unsorted files to sorted files.

        :param dicom_files:  A list of unsorted dicom filepaths.
        :type dicom_files: list
        :param output_dir:  Output directory
        :type output_dir: str
        :param mode: {'symbolic', 'copy', 'move'}. 
        :type mode: str
        :returns:  A list of filenames to the sorted and renamed dicoms.
    '''
    _module_logger.debug('received a call to organize_one_sequence')    
    try:
        _os.makedirs(output_dir)
    except OSError:
        _module_logger.warning('Directory exists.')

    if prefix is None:
        if isinstance( dicom_files, list):
            ds = dicom.read_file(dicom_files[0], stop_before_pixels=True)
        elif isinstance( dicom_files, str):
            ds = dicom.read_file(dicom_files, stop_before_pixels=True)
        sequence_info = get_sequence_info( ds )
        subject_id = get_subject_id( ds )
        prefix = '%s_%s' % (subject_id, sequence_info)
        ds = None
        del ds

    new_dicom_files = []
    for count, dcm in enumerate(dicom_files):
        # need to check the slice location and/or time points
        dcm_abspath = _os.path.abspath(dcm)
        new_dicom_files.append( _os.path.join(output_dir, '%s_%06d.dcm' % (prefix, count+1)))
        if mode == 'symbolic':
            # if link exists, force to overwrite (by removing first)
            if _os.path.islink(new_dicom_files[count]):
                _os.unlink(new_dicom_files[count])
            _os.symlink(dcm_abspath, new_dicom_files[count])
        elif mode == 'move':
            _shutil.move(dcm_abspath, new_dicom_files[count])
        elif mode == 'copy':
            _shutil.copyfile(dcm_abspath, new_dicom_files[count])
    return new_dicom_files

# how to do Dcm2nii args*?
def convert_one_sequence( dicom_files, output_dir, tmp_dir = None, prefix = None, orientation = 'LPS', **kwargs):
    ''' Convert given dicoms of *ONE* sequence in dicom_files into NIfTI compressed format with specified orientation to output_dir using dcm2nii program. Output filename will be <prefix>.<ext>.

        :param dicom_files: A list of dicom filepaths.
        :type dicom_files: list
        :param output_dir: Output directory.
        :type output_dir: str
        :param tmp_dir: A temporary directory for conversion. It will be deleted when the routine terminates.
        :type tmp_dir: str
        :param prefix: A prefix in string for the output files. Default is None. Dicom header information in the first file in dicom_files will be used as <PatientID>-<AcquisitionDate>_<SeriesDescription>-<SeriesNumber>.
        :type prefix: str
        :param orientation: A string of orientation. Default is 'LPS' (CBICA convention.)
        :type orientation: str
        :returns: A :class:`nipype.interfaces.dcm2nii.Dcm2nii` converter object.
    '''
    _module_logger.debug('received a call to convert_one_sequence')      
    # check dcm2nii executable 
    cmd = _find_executable('dcm2nii')
    if not cmd:
        raise OSError('dcm2nii command cannot be found in system path.')
        
    # from nipype import config
    # cfg = dict(logging=dict(workflow_level = 'NOTSET'))
    # config.update_config(cfg)
    from nipype.interfaces.dcm2nii import Dcm2nii # this might create another logging handler. 

    if not _os.path.isdir(output_dir):
        try:
            _os.makedirs(output_dir)
        except Exception, e:
            _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
            
    ## Create a tmpdir
    if not tmp_dir:
        tmp_dir = _tmp.mkdtemp(prefix = __name__,
                               dir = _os.environ['CBICA_TMPDIR'],
                               suffix = str(_uuid.uuid4()))
        to_remove_tmpdir = True # if tmp_dir not provided by user, it will be removed in the end
    else:
        to_remove_tmpdir = False

    _module_logger.debug('To remove temporary directory? ' + str(to_remove_tmpdir))
    
    _module_logger.info('%d dicoms in this sequence' % (len(dicom_files)))
    
    # Instantiate a new Dcm2nii converter
    converter = Dcm2nii()

    # Check if input dicom is of enhance format and is PCASL.
    # Need special care for Philips Enhance PCASL
    if isinstance( dicom_files, list):
        # TODO 20161011: should check all dicom files
        is_enhanced_dcm = [is_enhanced(dicom.read_file(f, stop_before_pixels=True)) for f in dicom_files]
        is_enhanced_dcm = any(is_enhanced_dcm)
        ds = dicom.read_file(dicom_files[0], stop_before_pixels=True)
    elif isinstance( dicom_files, str):
        ds = dicom.read_file(dicom_files, stop_before_pixels=True)
        dicom_files = [dicom_files]
        is_enhanced_dcm = is_enhanced( ds )

    sequence_info = get_sequence_info( ds )

    # If Enhanced, unenhance it first
    if is_enhanced_dcm:        
        _module_logger.warning('The input dicom is of enhanced type and needs special care.')
        dicom_files_classic = []
        for count, enhanced_dcm in enumerate(dicom_files):
            prefix_classic = '%s_%s_' % (sequence_info, count)
            classic_output_dir = _os.path.join(tmp_dir, sequence_info)
            try:
                dcm_classic = convert_enhance_to_classic( enhanced_dcm, output_dir = classic_output_dir, 
                                                          prefix = prefix_classic )
            except:
                _tb.print_exception(_sys.exc_info()[0],
                                    _sys.exc_info()[1],
                                    _sys.exc_info()[2])
                continue
            dicom_files_classic = dicom_files_classic + dcm_classic
            
        dicom_files = dicom_files_classic
        converter.inputs.convert_all_pars = True

    _module_logger.debug(str(len(dicom_files)) + ' dicoms in this sequence')

    if len(dicom_files) == 1:
        # convert only the given file, not every files in the directory
        # this is a work-around to address the issue that Dcm2nii will only
        # take the first file in the dicom_files
        converter.inputs.convert_all_pars = False

    converter.inputs.source_names = dicom_files
    converter.inputs.output_dir = tmp_dir
    converter.inputs.gzip_output= True
    converter.inputs.ignore_exception = True
    converter.inputs.date_in_filename = False
    converter.inputs.anonymize = False
    converter.inputs.reorient = False
    # check if default user dcm2nii config file exists
    default_config_file = _os.path.join( _os.path.expanduser('~'), '.dcm2nii', 'dcm2nii.ini' )
    if _os.path.exists(default_config_file):
        converter.inputs.config_file = default_config_file
    
    if kwargs.has_key('terminal_output'):
        converter.inputs.terminal_output = kwargs.get('terminal_output')
    elif _log.getLogger().getEffectiveLevel() > 10:
        converter.inputs.terminal_output = 'allatonce'
    elif _log.getLogger().getEffectiveLevel() == 10: # DEBUG mode
        converter.inputs.terminal_output = 'stream'
        

    # DEBUG/VERBOSE
    _module_logger.debug('dcm2nii command:\n' + converter.cmdline)

    try:
        converter.run()
    except Exception, e:
        _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
        if to_remove_tmpdir:
            # remove tmp_dir if failed
            _shutil.rmtree(tmp_dir)
        raise 'Unexpected error when running Dcm2nii.'
         
    if not hasattr(converter, 'output_files'):
        if to_remove_tmpdir:
            _shutil.rmtree(tmp_dir)
        raise RuntimeError('converter does not have output_files attribute. Something went wrong...')
    
    # Extract a prefix if not supplied
    if prefix is None:
        if isinstance( dicom_files, list):
            ds = dicom.read_file(dicom_files[0], stop_before_pixels=True)
        elif isinstance( dicom_files, str):
            ds = dicom.read_file(dicom_files, stop_before_pixels=True)
        sequence_info = get_sequence_info( ds )
        subject_id = get_subject_id( ds )
        prefix = '%s_%s' % (subject_id, sequence_info)
        ds = None
        del ds
    # create a copy of the original prefix for later use if there are multiple output_files
    prefix_orig = prefix
#    # check the consistency of output_files, bvals, and bvecs
#    if 'DTI' in sequence_info:
#        # converter.aggregate_outputs() is expected to fail in the case when DWI has extra directions.
#        num_bvecs = len(converter.bvecs)
#        num_bvals = len(converter.bvals)
#        num_output = len(converter.output_files)
#        if num_output > num_bvecs and num_output > num_bvals and num_bvals == num_bvecs:
#            # check the number of gradient directions in all output files
#            # throw out the longer one or name that doesn't have prefix.
#            is_file = map(_os.path.isfile, converter.output_files)
#            if not all(is_file):
#                # remove files that do not exist
#                good_file = [f for i, f in enumerate(converter.output_files) if is_file[i] is True]
#                converter.output_files = good_file
#            
#            num_gradients = [nib.load(f).shape[3] for f in converter.output_files]
#            nifti_with_fewest_gradient = converter.output_files[num_gradients.index(min(num_gradients))]
#            converter.output_files = nifti_with_fewest_gradient
#    else:
#        try:
#            converter.aggregate_outputs()
#        except Exception, e:
#            _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
#            if to_remove_tmpdir:
#                # remove tmp_dir if failed
#                _shutil.rmtree(tmp_dir)
#            raise 'Dcm2nii internal error. See traceback.'
        
        

    ##DEBUG##
    _module_logger.debug('number of output:' + str(len(converter.output_files)))
    ''' reorient the images (in most case, it should be dealing with only one image
        but when using DWI or T2 as search string, this function might get multiple DWIs,
        T2 + T2 Flair as input source_names. '''
    ''' Should test:
        1. input multiple sequences
        2. input DWI images with potential bval/bvec '''

    
    for i in xrange(len(converter.output_files)):
        ## convert_one_sequence expects only one sequence input
        ## (identical series description and series number)
        ## if there are more than one, append extra character in prefix
        if i > 0 and 'DTI' not in sequence_info:
            # TODO: throw a warning as this is not supposed to happen.
            # One sequence should have only one nifti output.
            import string as _string
            prefix = '%s_%s' % (prefix_orig, _string.ascii_uppercase[ i - 1 ])
            
        output_filename = _os.path.split(converter.output_files[i])[1]
        output_renamed = _os.path.join(output_dir, prefix + '.nii.gz')
        bval_filename = []
        bvec_filename = []
        bval_renamed = []
        bvec_renamed = []

        _module_logger.debug('output_filename %d/%d: %s' % (i+1, len(converter.output_files), output_filename))
        # use output_filename to match bval and bvec
        # bval and bvec contains only the basename
        # if bval and bvec attributes are not empty...
        if converter.bvals and converter.bvecs:
            # try to find bval and bvec that correspond to the output dwi file
            # bval_filename and bvec_filename are both tuple of index of the
            # file in converter and the filename
            
            bval_filename = [[index, fn] for index, fn in enumerate(converter.bvals)
                            if output_filename.split('.')[0] in fn]
            bvec_filename = [[index, fn] for index, fn in enumerate(converter.bvecs)
                            if output_filename.split('.')[0] in fn]
            _module_logger.debug('bval_filename is ' + bval_filename[0][1])
            _module_logger.debug('bvec_filename is ' + bvec_filename[0][1])
            
            # if any found, define the new output names and rename the bval first
            if (bval_filename and _os.path.isfile(bval_filename[0][1])) and (bvec_filename and _os.path.isfile(bvec_filename[0][1])):
                # add a sanity check to see if the number of gradients agree among files.
                count_bval = len([l.strip().split(' ') for l in open(bval_filename[0][1], 'r')][0])
                count_gradient = nib.load(converter.output_files[i]).shape[3]
                if count_bval != count_gradient:
                    raise RuntimeError('Number of direction gradients do not match between bval and Nifti file.')
                    
                bval_renamed = _os.path.join(output_dir, prefix + '.bval')
                bvec_renamed = _os.path.join(output_dir, prefix + '.bvec')
            
                _shutil.move(bval_filename[0][1], bval_renamed)
                converter.bvals[ bval_filename[0][0] ] = bval_renamed
            elif (bval_filename and not _os.path.isfile(bval_filename[0][1])) and (bvec_filename and not _os.path.isfile(bvec_filename[0][1])):
                # if there are bval and bvec and files don't exist, try another file with prefix "x"
                # this would be the case when converted DWI image contains extra direction/4th dimension image
                # dcm2nii would cut the extra direction in the text files and in the converted DWI Nifti image
                # However, the nipype.interfaces.dcm2nii converter would still place the original bval/bvec in
                # the converter.bvals and bvecs.
                head, tail = _os.path.split(bval_filename[0][1])
                alt_bval_filename = _os.path.join(head, 'x' + tail)
                head, tail = _os.path.split(bvec_filename[0][1])
                alt_bvec_filename = _os.path.join(head, 'x' + tail)
                
                if _os.path.isfile(alt_bval_filename) and _os.path.isfile(alt_bvec_filename):
                    converter.bvals[ bval_filename[0][0] ] = alt_bval_filename
                    converter.bvecs[ bvec_filename[0][0] ] = alt_bvec_filename
                    continue
#                        bval_filename[0][1] = alt_bval_filename
#                        bvec_filename[0][1] = alt_bvec_filename
#                        bval_renamed = _os.path.join(output_dir, prefix + '.bval')
#                        bvec_renamed = _os.path.join(output_dir, prefix + '.bvec')
#                    
#                        _shutil.move(bval_filename[0][1], bval_renamed)
#                        converter.bvals[ bval_filename[0][0] ] = bval_renamed
                else:
                    # if no bval and bvec files found for this output_filename, then throw an error
                    raise RuntimeError('Cannot find matching bval and bvec files for this output sequence ' + output_filename)
                
        if orientation == 'LAS':
            # Dcm2nii by default gives LAS orientation
            _shutil.move(converter.output_files[i], output_renamed)
            if bvec_filename:
                _shutil.move(bvec_filename[0][1], bvec_renamed)
                converter.bvecs[ bvec_filename[0][0] ] = bvec_renamed
        else:
            # reorient the image and bvec if any is associated
            import numpy as _np
            from orientation import reorient_nifti_and_bvec
            
            nii_orig = nib.load(converter.output_files[i])
            if bvec_filename:
                bvec_orig = _np.loadtxt(bvec_filename[0][1])
                nii_reoriented, bvec_reoriented = reorient_nifti_and_bvec(nii_orig,
                                                                          orientation = orientation,
                                                                          bvec = bvec_orig)
                _np.savetxt(bvec_renamed, bvec_reoriented, delimiter = ' ')
                _os.remove(bvec_filename[0][1])
                converter.bvecs[ bvec_filename[0][0] ] = bvec_renamed
            else:
                nii_reoriented = reorient_nifti_and_bvec(nii_orig,
                                                         orientation = orientation)
            _os.remove(converter.output_files[i])
            nii_reoriented.to_filename(output_renamed)
            
        converter.output_files[i] = output_renamed

    ## Select the ones that are finally converted to output_dir
    converter.output_files = [file_in_outputdir for file_in_outputdir in converter.output_files 
                                               if output_dir in file_in_outputdir]
    ## clean up enhance_to_classic files
#    if 'dicom_files_classic' in locals() and dicom_files_classic and to_remove_tmpdir:
#        _shutil.rmtree(_os.path.dirname(dicom_files_classic[0]))
    if to_remove_tmpdir:
        _shutil.rmtree(tmp_dir)

    return converter

def convert_enhance_to_classic(src_dcm, output_dir = None, prefix = None):
    ''' Unenhance the src_dcm, return a list of unenhanced dicoms.

        :param src_dcm: A enhanced dicom filepath.
        :type src_dcm: str
        :param output_dir: Output directory to save the unenhanced dicoms. Will create a temporary directory if None.
        :type output_dir: str
        :param prefix: A string as a prefix for output unenhanced files.
        :type prefix: str
        :returns: A list of unenhanced dicoms.
    '''
    _module_logger.debug('received a call to convert_enhance_to_classic')    
    # check dcuncat executable
    cmd = _find_executable('dcuncat')
    if not cmd:
        raise OSError('dcuncat command cannot be found in system path.')

    import subprocess as _subp

    if output_dir is None:    
        output_dir = _tmp.mkdtemp(prefix = __name__,
                                  dir = _os.environ['CBICA_TMPDIR'],
                                  suffix = str(_uuid.uuid4()))

    if not _os.path.isdir(output_dir):
        try:
            _os.makedirs(output_dir)
        except Exception, e:
            _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])

    if prefix is None:
        prefix = 'enhance_to_classic_'

    cmd = [cmd, '-unenhance', '-of', _os.path.join(output_dir, prefix), src_dcm]
    stdout, stderr = _subp.Popen(cmd, stdout = _subp.PIPE, stderr = _subp.PIPE).communicate()
    src_dcms_classic = discover_files(output_dir)

    return src_dcms_classic

def convert_one_directory( input_dir, output_dir, log = None, tmp_dir = None, keyword = None, exclude = None,
                           recursive = True, orientation = 'LPS', mode = 'symbolic', force = False,
                           group_by = ['SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription'], **kwargs):
    ''' Finds all dicoms recursively in a given directory, parse_and_group them, filter the sequences
        with include and exclude keywords, get grouped dicoms for each sequence, call 
        :func:`dicom2nifti.convert_one_sequence` in a loop to convert dicoms to nifti images (as nii.gz format). This 
        routine will create dicoms and Nifti directories in the output_dir and a nifti log at log.
        
        :param input_dir:  A directory containing dicoms.
        :type input_dir: str
        :param output_dir:  Output directory. 
        :type output_dir: str
        :param log:  An output filepath of the log file. If log does not exist, a new file will be created.
        :type log: str
        :param keyword:  A list of case insensitive search string for specific sequence in a dcm_groups. Ex. ['T1', 'DWI'].
        :type keyword: str or list of strings
        :param exclude:  A list of case insensitive search string for excluding specific sequence in a dcm_groups. Ex. ['localizer', 'moco']
        :type exclude: str or list of strings
        :param recursive:  If True, finds dicoms recursively in input_dir. Default is True.
        :type recursive: boolean
        :param orientation:  A string of orientation. Default is 'LPS' (CBICA convention.)
        :type orientation: str
        :param mode: {'symbolic', 'copy', 'move', 'skip'}.
        :type mode: str
        :param force: Force sorting and converting even if the sequence exists in the log file and overwrite.
        :type mode: boolean
        :param group_by:  A list of case sensitive search dicom tag names to group dicoms.
        :type group_by: str or list of strings
        :param kwargs: Additional keyword arguments for :class:`nipype.interfaces.dcm2nii.Dcm2nii` object.
    '''
    _module_logger.debug('received a call to convert_one_directory')      
    # check dcm2nii executable
    from distutils.spawn import find_executable   
    cmd = _find_executable('dcm2nii')
    if not cmd:
        raise OSError('dcm2nii command cannot be found in system path.')
        
    dicom_output_dir = _os.path.join(output_dir, 'dicoms')
    nifti_output_dir = _os.path.join(output_dir, 'Nifti')
    
    ## Create a tmpdir
    if not tmp_dir:       
        tmp_dir = _tmp.mkdtemp(prefix = __name__,
                               dir = _os.environ['CBICA_TMPDIR'],
                               suffix = str(_uuid.uuid4()))
        to_remove_tmpdir = True # if tmp_dir not provided by user, it will be removed in the end
    else:
        to_remove_tmpdir = False

    _module_logger.info('Crawling the input directory to find dicoms')
    src_dcms = discover_files( input_dir, recursive = recursive )
    _module_logger.info('%d dicoms found.' % (len(src_dcms)))
    
    _module_logger.info('Grouping dicoms. It might take a while...')
    dcm_groups = get_all_dicom_groups( src_dcms, group_by = group_by )

    _module_logger.info('Sequences found %s:' % (group_by))
    for k in dcm_groups.iterkeys():
        _module_logger.info('%s' % (str(k)))
    _module_logger.info('Filtering dicoms based on:\nSearch keyword = %s\nExclude keyword = %s' % (str(keyword), str(exclude)))
    dcm_selected_groups = get_all_dicoms_from_sequences( dcm_groups,
                                keyword = keyword, exclude = exclude)
    ## recycle the memory
    dcm_groups = None
    del dcm_groups
    
    for key, src_dcms in dcm_selected_groups.iteritems():
        #sequence = sequence.replace(' ', '_').replace('/','_').replace('(','').replace(')','').replace('*', '').replace('&', '').replace('$', '').replace(':', '.')
        tmp_ds = dicom.read_file(src_dcms[0], stop_before_pixels=True)
        sequence = get_sequence_info(tmp_ds)
        subject_id = get_subject_id(tmp_ds)

        _module_logger.info('Working on %s %s' % (subject_id, sequence))
        ## query if nifti files of the given sequence and subect_id exists
        ## in the log and in the filesystem
        if log:
            import pandas as _pd
            import logger
            import lockfile # This is the API in 0.8.0, in 0.9.1, it's LockFile, in 2.0.5 it's filelock
            lock = lockfile.FileLock(log)
            lock.timeout = 3600
            if not force:
                try:
                    with lock: ## argument poll_intervall not available in this version of lockfile
                        if _os.path.exists(log):
                            df_nifti_log = _pd.read_csv(log, index_col = 0)
                            isconverted = logger.is_converted(df_nifti_log, subject_id, sequence)
                            if isconverted:
                                _module_logger.warning('%s %s already converted' % (subject_id, sequence))
                                continue
                except lockfile.LockTimeout:
                    # Create an new, unique CSV for this routine
                    # If a lock cannot be acquired, log it in Nifti subject directory instead
                    log = _os.path.join(nifti_output_dir, subject_id, subject_id + '.csv')
                    _module_logger.warning('Lock timeout. Log the entry to ' + log)
                    if _os.path.exists(log):
                        df_nifti_log = _pd.read_csv(log, index_col = 0)
                        isconverted = logger.is_converted(df_nifti_log, subject_id, sequence)
                        if isconverted:
                            _module_logger.warning('%s %s already converted' % (subject_id, sequence))
                            continue
        
        subject_sequence_dicom_dir = _os.path.join(dicom_output_dir, subject_id, sequence)
        subject_nifti_dir = _os.path.join(nifti_output_dir, subject_id)
        prefix = '%s_%s' % (subject_id, sequence)

        if mode != 'skip':
            _module_logger.info('Sorting %s %s' % (subject_id, sequence))
            try:
                new_dicom_files = organize_one_sequence( src_dcms, subject_sequence_dicom_dir,
                                                         prefix = prefix, mode = mode )
            except:
                _module_logger.error('Error occurred when sorting %s %s:' % (subject_id, sequence))
                _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
                new_dicom_files = src_dcms # this will definitely be unused
                if log:
                    logger.log_tofile(log, subject_id, sequence, msg = 'SORT_FAILED')
                continue                
        else:
            new_dicom_files = src_dcms

        # Check if the filename is longer than 255, the limit dcm2nii has.
        if len(new_dicom_files[0]) >= 255 and len(src_dcms[0]) < 255:
            new_dicom_files = src_dcms
        elif len(new_dicom_files[0]) >= 255 and len(src_dcms[0]) >= 255:
            tmp_sequence_dir = _os.path.join(tmp_dir, subject_id, sequence)
            _os.makedirs(tmp_sequence_dir)
            [_os.symlink(src_dcms[i], _os.path.join(tmp_sequence_dir, '%s.dcm' % (i))) for i in len(src_dcms)]
            new_dicom_files = discover_files(tmp_sequence_dir)

        _module_logger.info('Converting %s %s' % (subject_id, sequence))
        try:
            converter = convert_one_sequence( new_dicom_files, subject_nifti_dir,
                                              prefix = prefix,
                                              orientation = orientation,
                                              tmp_dir = tmp_dir,
                                              **kwargs)
        except:
            _module_logger.error('Error occurred when converting %s %s:' % (subject_id, sequence))
            _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
            if log:
                logger.log_tofile(log, subject_id, sequence, msg = 'CONVERT_FAILED')
            continue

        # log it!
        # TODO: what about multiple outputs?
        if log:
            if len(converter.output_files) == 1:
                logger.log_tofile(log, subject_id, sequence, nifti_path = converter.output_files[0])
            elif len(converter.output_files) > 1:
                logger.log_tofile(log, subject_id, sequence, msg = ' '.join(converter.output_files))
            else:
                logger.log_tofile(log, subject_id, sequence, msg = 'NA')

    if to_remove_tmpdir:
        _shutil.rmtree(tmp_dir)
