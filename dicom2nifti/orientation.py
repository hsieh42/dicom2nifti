#!/usr/bin/env python
__author__ = 'HsiehM'

import logging as _log
import nibabel as _nib
import numpy as _np

_module_logger = _log.getLogger(__name__)
_ch = _log.StreamHandler()
_formatter = _log.Formatter(fmt = '%(asctime)s %(name)s %(levelname)s: %(message)s',
                            datefmt = '%Y%m%d-%H:%M:%S')
_ch.setFormatter(_formatter)
_module_logger.addHandler(_ch) 

def reorient_nifti_and_bvec( nii, orientation = 'LPS', bvec = None):
    ''' Reorient the image from original orientation in nii to a given orientation. 
    
        :param nii: A nifti image to be reoriented.
        :type nii: nibabel.nifti1.Nifti1Image
        :param orientation: A nifti image orientation in a string using CBICA "to" convention.
        :type orientation: str
        :param bvec: A 3 x N array of gradient vectors.
        :type bvec: numpy.array
        :returns: nii_oriented if bvec is not supplied. 
        :returns: (nii_oriented, bvec_oriented) if bvec is supplied. 
    '''
    
    _module_logger.debug('received a call to reorient_nifti_and_bvec')
    
    if not _is_valid_orientation(orientation):
        pass

    nii_affine = nii.get_affine()
    nii_data = nii.get_data()
    new_orient_code = tuple(orientation.upper())
    orig_orient_code = _nib.aff2axcodes(nii_affine)
    new_orient_ornt = _nib.orientations.axcodes2ornt(new_orient_code)
    orig_orient_ornt = _nib.orientations.axcodes2ornt(orig_orient_code)
    trans_ornt = _nib.orientations.ornt_transform(orig_orient_ornt,
                                                  new_orient_ornt)
    nii_data_reoriented = _nib.apply_orientation(nii_data, trans_ornt)
    trans_affine = _nib.orientations.inv_ornt_aff(trans_ornt, nii.shape)
    nii_affine_reoriented = _np.dot(nii_affine, trans_affine)
    nii_reoriented = _nib.Nifti1Image(nii_data_reoriented,
                                      nii_affine_reoriented,
                                      header = nii.get_header())
    
    nii_reoriented.set_qform(nii_reoriented.get_sform())
    
    if bvec is not None:
        bvec = _np.array(bvec).T
        bvec_out = _np.dot(bvec, trans_affine[0:3,0:3])
        bvec_out = bvec_out.T
        return (nii_reoriented, bvec_out)

    return nii_reoriented

def _is_valid_orientation(orientation):
    ''' Check if a nifti orientation is valid. The orientation has to have three unique letters
        for three dimensional data, one for each dimension: left-right, anterior-posterior and
        superior-inferior.
        
        :param orientation: A nifti image orientation using CBICA "to" convention.
        :type orientation: str
        :returns: True if input string is a valid orientation.
    '''
    orientation = [s.upper() for s in orientation]

    # if the string is shorter than three, fail it.
    if len(''.join(orientation)) != 3:
        return False
    
    LR = False
    AP = False
    SI = False
    LRnotTwice = True
    APnotTwice = True
    SInotTwice = True
    
    for o in orientation:
        if o in ('R','L'):
            if LR:
                LRnotTwice = False
            LR = True
        elif o in ('A','P'):
            if AP:
                APnotTwice = False
            AP = True
        elif o in ('S','I'):
            if SI:
                SInotTwice = False
            SI = True
    is_valid = (LR and AP and SI and LRnotTwice and APnotTwice and SInotTwice)
    return is_valid
