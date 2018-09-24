# dicom2nifti
Sorting DICOM and conversion to NIfTI format used in CBICA and CBIG.

## Software dependency
Developed and tested on python 2.7.x. Requires dcm2nii from mricron/7.7.12 or newer, best with mricron/2015.06.01.

## Installation
It is best to install the package in a virtual environment if you want to have full control over the environment or don't have system administrative privilege. Go to the source directory and do
```bash
python setup.py install
```
This will install all the dependencies and the source code to your environment.

If you want the latest codes installed, you can do
```bash
pip install -U git+https://github.com/hsieh42/dicom2nifti.git
```
However there might be undocumented features.

## Usage
### Command line mode

### Interactive mode
To use the package, make sure that the package path where this README.rst is is in your python path.
```python
import sys
sys.path.append('/path/to/this/package/')
import dicom2nifti as dcmnii
idir='/path/to/raw/dicoms/'
odir='/path/to/save/output/'
log='/path/to/save/log.csv'
orientation='LPS'
dcmnii.convert_one_directory(idir, odir, log=log, orientation=orientation)
```
To convert sequences selectively:
```python
include = ['T1', 'DTI', 'FLAIR']
exclude = ['Moco', 'localizer']
dcmnii.convert_one_directory(idir, odir, log=log, orientation=orientation, keyword=include, exclude=exclude)
```

