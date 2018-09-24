# dicom2nifti
Sorting DICOM and conversion to NIfTI format used in CBICA and CBIG. 

## Software dependency
Developed and tested in python 2.7.x on cbica-cluster (linux) only. Requires `dcm2nii` executable (from `mricron/7.7.12` on cbica-cluster or newer, best with mricron/2015.06.01). 

## Installation
It is best to install the package in a virtual environment if you want to have full control over the environment or don't have system administrative privilege. Go to the source directory and do
```bash
python setup.py install
```
This will install all the dependencies and the source package to your environment. `sortAndRenameDicoms` and `rename_nifti` are the two executable scripts that will be installed. 

If you want the latest codes installed, you can do
```bash
pip install -U git+https://github.com/hsieh42/dicom2nifti.git
```
However there might be undocumented features.

## Usage
### Command line mode
A very basic example of the usage would be:
```bash
mkdir ${output_dir}
sortAndRenameDicoms -i ${input_unsorted_dicom_dir} \
                    -o ${output_dir} \
                    -l ${output_dir}/test_log.csv \
                    -r LPS \
                    -g SeriesInstanceUID SeriesNumber SeriesDescription \
                    -e T1 T2 \
                    -E low_res \
                    -m symbolic
```
This command would perform sort, rename, and convert input DICOM in `$input_unsorted_dicom_dir` into NIfTI images of LPS orientation in `$output_dir` along with a log file `test_log.csv`. DICOM files will be grouped by three tags: SeriesInstanceUID, SeriesNumber, and SeriesDescription. `-e` and `-E` options are used to filter the series based on its SeriesDescription value. In this example, `T1` and `T2` will be selected while anything containing `low_res` will be excluded from sorting and conversion. For example, `T1_low_res` and `flair_low_res` will be excluded while `T1_high_res` and `T2_motion` will be included. The mode `symbolic` will create symbolic links for the sorted DICOM to the original files.


### Interactive mode
The following codes would achieve the same goal as the example above interactively.
```python
import dicom2nifti as dcmnii
# take input_unsorted_dicom_dir, output_dir and log from the last example
orientation='LPS'
include = ['T1', 'T2']
exclude = ['low_res']
mode = 'symbolic'
group_by = ['SeriesInstanceUID', 'SeriesNumber', 'SeriesDescription']
dcmnii.convert_one_directory(input_unsorted_dicom_dir, output_dir, log = log, orientation = orientation, 
                             keyword = include, exclude = exclude, mode = mode, group_by = group_by)
```

