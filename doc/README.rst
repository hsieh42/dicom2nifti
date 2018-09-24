Basic usage
===========

Software dependency:
mricron/7.7.12 or newer. Best with mricron/2015.06.01.

Interactive mode:
To use the package, make sure that the package path where this README.rst is is in your python path.

>>> import sys
>>> sys.path.append('/path/to/this/package/')
>>> import dicom2nifti as dcmnii
>>> idir='/path/to/raw/dicoms/'
>>> odir='/path/to/save/output/'
>>> log='/path/to/save/log.csv'
>>> orientation='LPS'
>>> dcmnii.convert_one_directory(idir, odir, log=log, orientation=orientation)

To convert sequences selectively:

>>> include = ['T1', 'DTI', 'FLAIR']
>>> exclude = ['Moco', 'localizer']
>>> dcmnii.convert_one_directory(idir, odir, log=log, orientation=orientation, keyword=include, exclude=exclude)



Todo
----

* Convert nifti in tmpdir.
* Just sort.
* Just convert.
