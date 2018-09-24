import logging as _log
import os as _os
import sys as _sys
import traceback as _tb
from datetime import datetime as _dt
import pandas as pd
import numpy as _np

_module_logger = _log.getLogger(__name__)
_ch = _log.StreamHandler()
_formatter = _log.Formatter(fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s',
                            datefmt = '%Y%m%d-%H:%M:%S')
_ch.setFormatter(_formatter)
_module_logger.addHandler(_ch) 

def is_converted(df, subject_id, sequence):
    ''' Check if a given subject_id and sequence pair has been converted into a nifti image.
        
        :param df: A dataframe created by dicom2nifti.logger.create_log() that
                   has 'ID' as index name and sequences as column names.
        :type df: pandas.DataFrame
        :param subject_id: A subject identifier to query from df.
        :type subject_id: str
        :param sequence: A sequence to query from df.
        :type sequence: str
        :returns: True if a valid nifti file can be found in the df.
    '''
    _module_logger.debug('received a call to is_converted')
    # what to do when there are more than one file in the cell?
    # they will be delimited by spaces
    if sequence in df.columns and subject_id in df.index:
        outcome = df[sequence][subject_id]
        # outcome could be nan
        try:
            isfile = _os.path.exists(outcome)
        except:
            isfile = False
        return isfile
    else:
        return False

def log_tofile(filename, subject_id, sequence, **kwargs):
    ''' Log a custome string to subject_id row and sequence column and update the 
        timestamp in Time_Last_Update column in a dataframe and in the end save the 
        dataframe to file. The timestamp format:'%Y/%m/%d-%H:%M:%S'.
        
        :param filename: A dataframe created by :func:`dicom2nifti.logger.create_log` that
                   has 'ID' as index name and Time_Last_Update and sequences as column names.
        :type df: pandas.DataFrame
        :param string: text/message to log.
        :type string: str
        :param subject_id: A subject identifier to be added to rows.
        :type subject_id: str
        :param sequence: A sequence to be added to columns.
        :type sequence: str

    '''
    
    _module_logger.debug('received a call to log_tofile')
    
    import lockfile
    lock = lockfile.FileLock(filename)
    lock.timeout = 3600
    try:
        with lock:  ## argument poll_intervall for acquire() not available in this version of lockfile
            if _os.path.exists(filename):
                df_nifti_log = pd.read_csv(filename, index_col = 0, dtype = str)
            else:
                df_nifti_log = create_log()
                
            log_conversion(df_nifti_log, subject_id, sequence, inplace = True, **kwargs)
            df_nifti_log.to_csv(filename, index = True)

    except lockfile.LockTimeout:
        # lock.unique_name: hostname-tname.pid-somedigits
        unique_name = _os.path.split(lock.unique_name)[1]
        filename_tmp = filename + '_' + unique_name
        _module_logger.warning('Lock timeout. Log the entry to ' + filename_tmp)
        
        if _os.path.exists(filename_tmp):
            df_nifti_log = pd.read_csv(filename_tmp, index_col = 0, dtype = str)
        else:
            df_nifti_log = create_log()
            
        log_conversion(df_nifti_log, subject_id, sequence, inplace = True, **kwargs)
        df_nifti_log.to_csv(filename_tmp, index = True)
#    except:
#        _tb.print_exception(_sys.exc_info()[0], _sys.exc_info()[1], _sys.exc_info()[2])
        
    return 0
        
    
        
def log_conversion( df, subject_id, sequence, nifti_path = None, msg = None, inplace = False ):
    ''' Log a nifti image (filename) to subject_id row and sequence column and update the 
        timestamp in Time_Last_Update column. The timestamp format:'%Y/%m/%d-%H:%M:%S'.
        
        :param df: A dataframe created by :func:`dicom2nifti.logger.create_log` that
                   has 'ID' as index name and Time_Last_Update and sequences as column names.
        :type df: pandas.DataFrame
        :param nifti_path: A nifti file path.
        :type nifti_path: str
        :param subject_id: A subject identifier to be added to rows.
        :type subject_id: str
        :param sequence: A sequence to be added to columns.
        :type sequence: str
        :param inplace: To modify the dataframe in place, default False. If True, in place.
        :type inplace: boolean
        :rtype: pandas.DataFrame
    '''
    _module_logger.debug('received a call to log_conversion')
    
    if not (nifti_path or msg):
        raise 'Both nifti_path and msg are not specified. At least one needs to be specified.'
    elif nifti_path:
        if not _os.path.exists(nifti_path):
            raise IOError('Input argument nifti_path: ' + nifti_path + ' does not exist.')
        else:
            entry = nifti_path
    elif msg and not nifti_path:
        entry = msg
        
    if inplace:
        df.at[subject_id, sequence] = entry
        df.at[subject_id, 'Time_Last_Update'] = _dt.now().strftime('%Y/%m/%d-%H:%M:%S')
        return df
    else:
        df_out = df.copy()
        df_out.at[subject_id, sequence] = entry
        df_out.at[subject_id, 'Time_Last_Update'] = _dt.now().strftime('%Y/%m/%d-%H:%M:%S')
        return df_out
        
#    if _os.path.exists(nifti_path):
#        if inplace:
#            df.at[subject_id, sequence] = nifti_path
#            df.at[subject_id, 'Time_Last_Update'] = _dt.now().strftime('%Y/%m/%d-%H:%M:%S')
#            return df
#        else:
#            df_out = df.copy()
#            df_out.at[subject_id, sequence] = nifti_path
#            df_out.at[subject_id, 'Time_Last_Update'] = _dt.now().strftime('%Y/%m/%d-%H:%M:%S')
#            return df_out
#    else:
#        raise IOError('Input argument nifti_path: ' + nifti_path + ' does not exist.')

def create_log():
    ''' Instantiate a new :class:`pandas.DataFrame` object with specific format for logging. The returned
        df has 'ID' as index name and one column: Time_Last_Update.
        
        :rtype: pandas.DataFrame
    '''
    _module_logger.debug('received a call to create_log')
    
    df = pd.DataFrame(columns = ['Time_Last_Update'], dtype = str)
    df.index.name = 'ID'
    return df
    

def _combine_cells(cell_x, cell_y):
    ''' Return a combined cell value from two cells depending on whether the cell is empty or NaN.
        If cell_x is empty/NaN, return cell_y. If both cells are not empty/NaN, combine them delimited
        with a space. Otherwise, return cell_x.
        
        :param cell_x: A cell value from a pandas.DataFrame object.
        :type cell_x: str
        :param cell_y: A cell value from a pandas.DataFrame object.
        :type cell_y: str
        :returns: A combined cell value.
    '''
    
#    if not pd.isnull(cell_x) and not pd.isnull(cell_y):
#        if _os.path.exists(cell_x) and _os.path.exists(cell_y):
#            return cell_x + ' ' + cell_y
#    elif pd.isnull(cell_y) or not _os.path.exists(cell_y):
#        return cell_x
#    elif pd.isnull(cell_x) or not _os.path.exists(cell_x):
#        return cell_y
    #_module_logger.debug("cell_x is " + str(cell_x))
    #_module_logger.debug("cell_y is " + str(cell_y))
        
    if all(map(_os.path.exists, str(cell_x).split(' '))) and all(map(_os.path.exists, str(cell_y).split(' '))):
        return cell_x + ' ' + cell_y
    elif all(map(_os.path.exists, str(cell_x).split(' '))) and not all(map(_os.path.exists, str(cell_y).split(' '))):
        return cell_x
    elif all(map(_os.path.exists, str(cell_y).split(' '))) and not all(map(_os.path.exists, str(cell_x).split(' '))):
        return cell_y
    else:
        return pd.np.nan
#    if not (pd.isnull(cell_x) or pd.isnull(cell_y)):
#        return cell_x + ' ' + cell_y
#    elif pd.isnull(cell_x):
#        return cell_y
#    elif pd.isnull(cell_y):
#        return cell_x
    
def merge_log_by_modality(df, modalities = {'T1': ['T1'], 'T2': ['T2'], 'FLAIR': ['FLAIR'], 'DTI': ['DTI', 'DWI'], 'PCASL': ['PCASL'], 'RESTING': ['REST', 'RSFMRI'], 'BOLD_BREATHHOLD':['BREATH', 'HOLD', 'HELD']}):
    ''' Merge multiple columns of similar series in a :class:`pandas.DataFrame` into one column. 
        
        :param df: A dataframe created by dicom2nifti.logger.create_log() that
                   has 'ID' as index name and sequences as column names.
        :type df: pandas.DataFrame
        :param modalities: A dict of modality (series) as key and a list of keywords as value to group log columns.
        :type modalities: dict
        :returns: A merged :class:`pandas.DataFrame`.
    '''
    df_merged = create_log()
    
    # find columns that contains specific keyword.
    for modality, keywords in modalities.iteritems():
        modality = modality.upper()
        keywords = [i.upper() for i in keywords]
        if modality == 'T2':
            # don't select T2_FLAIR and T2_Quick
            cols = [i for i in df.columns for keyword in keywords if keyword in i.upper() and 'FLAIR' not in i.upper() and 'QUICK' not in i.upper()]
        elif modality == 'PCASL':
            # don't select pcasl_calibration
            cols = [i for i in df.columns for keyword in keywords if keyword in i.upper() and 'CALI' not in i.upper() and 'M0' not in i.upper()]
        elif modality == 'DTI':
            # don't select pcasl_calibration
            cols = [i for i in df.columns for keyword in keywords 
                      if keyword in i.upper() and 'TRACE' not in i.upper() and 'FADTI' not in i.upper() and 
                         'EDTI' not in i.upper() and 'DDTI' not in i.upper() and 'ISODTI' not in i.upper()]
        else:
            cols = [i for i in df.columns for keyword in keywords if keyword in i.upper()]
            
        cols = list(set(cols))   
         
        if not cols:
            _module_logger.warning('No matching column for modality ' + str(modality))
            continue
        else:
            _module_logger.info('columns selected with keyword ' + str(modality) + ' are ' + ', '.join(cols))

        #df_selected = df[cols]
        tmp = df[cols[0]].astype(str)  # TODO 20160830 If the first column returns all NaN, dtype will be float and will be imcompatible to any strings that follow.
        #_module_logger.debug(tmp)
        
        # And put the selected columns together.
        #import pdb; pdb.set_trace()
        for i in range(1, len(cols)):
            #try:
                #df_exist = df[cols[i]].applymap(_os.path.exists)
            #_module_logger.debug(df[cols[i]])
            
            tmp = tmp.combine(df[cols[i]], _combine_cells)
            #except:
            #    _module_logger.warning(str(cols[i]) + ' somehow failed.')
        df_merged[modality] = tmp
    
    df_merged.ix[:, 'Time_Last_Update'] = _dt.now().strftime('%Y/%m/%d-%H:%M:%S')
    
    return df_merged
    
def count_files(s):
    ''' Count number of valid file in a string. Typical use is to apply the function on the cells in a dataframe. 
        Ex. df.applymap(count_files)
        
        :param s: A string.
        :returns: A count of valid files.
    '''
    if isinstance(s, str):
        count = _np.zeros(len(s.split(' ')), dtype = int)
        for i, f in enumerate(s.split(' ')):
            try:
                count[i] = _os.path.exists(f)
            except:
                count[i] = False
        return count.sum()
    else:
        return 0
        
