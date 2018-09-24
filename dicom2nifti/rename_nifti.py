#!/usr/bin/env python
__author__ = 'HsiehM'
__EXEC__ = __file__

# Import modules here
import os, sys

def create_parser():
    import argparse
    ''' Create an argparse.ArgumentParser object

        :returns: An argparse.ArgumentParser parser.
    '''
    parser = argparse.ArgumentParser(prog = __EXEC__,
                                     description = 'Create/Update renamed nifti files and master sheet (master.csv) with a consolidated CSV files (merged.csv) containing nifti file paths. Support adding new cases. Does not support removing cases yet.')
    # Required
    parser.add_argument('-i', '--inputcsv',
                        required = True,
                        dest = 'inputcsv',
                        action = 'store',
                        type = str,
                        help = 'Input the merged CSV file that contains file paths for each modality. First column of the CSV is assumed to be subject ID column.')

    # Optional
    parser.add_argument('-l', '--output_master',
                        dest = 'master',
                        action = 'store',
                        default = None,
                        type = str,
                        help = 'Output master CSV.')
    parser.add_argument('-o', '--outputdir',
                        dest = 'odir',
                        action = 'store',
                        default = None,
                        type = str,
                        help = 'Output directory for renamed Nifti files. Softlinks will be created in each directory.')
    parser.add_argument('-m', '--modality',
                        dest = 'modality',
                        action = 'store',
                        default = None,
                        nargs='+',
                        help = 'Only convert series containing these string (case-sensitive)')
    parser.add_argument('-p', '--pid_column',
                        dest = 'pid',
                        action = 'store',
                        default = None,
                        help = 'Input a column name within the master CSV')
    parser.add_argument('--execute',
                        dest = 'is_dry_run',
                        action = 'store_false',
                        default = True,
                        help = 'If called, softlinks will be created. Otherwise, program only prints out the intended renamed file paths.')
    return parser


def main(argv = None):
    if argv is None:
        argv = sys.argv[1:]
    # parse input from command line
    parser = create_parser()
    args = parser.parse_args(argv)
    
    import socket, time

    exe_folder = os.getcwd()
    exe_time = time.strftime("%Y-%m-%d %a %H:%M:%S", time.localtime())
    host = socket.gethostname()
    print "Command", __EXEC__
    print "Arguments", args
    print "Executing on", host
    print "Executing at", exe_time
    print "Executing in", exe_folder
    
    # Start your program
    import pandas as pd
    from datetime import datetime as dt
    
    df = pd.read_csv(args.inputcsv, index_col = 0)
    
    if args.modality is None:
        modality = df.columns.tolist()
        if 'Time_Last_Update' in modality:
            modality.remove('Time_Last_Update')
    else:
        modality = args.modality
    
    if args.master is not None:
        print "Working on Master sheet"
        no_master = True
        df_master_new = create_master(df, cols = modality)
        if os.path.isfile(args.master):
            no_master = False
            data_types = {i: int for i in modality}
            df_master = pd.read_csv(args.master, index_col = 0, dtype = data_types)
            
            if args.pid is not None:
                df['pid'] = df_master[args.pid]
            
            ordered_cols = df_master.columns.tolist()
            df_master_updated = df_master.copy()
            df_master_updated.update(df_master_new) # TODO 20160830 This does not add new cases
            # Add new cases
            is_new = ~df_master_new.index.isin(df_master.index)
            df_master_updated = pd.concat([df_master_updated, df_master_new.ix[is_new]], axis = 0)
            
            # TODO 20160830 Remove cases
            #to_remove = ~df_master.index.isin(df_master_new)
            
            # Check what's updated
            is_in_original = df_master_updated[modality].isin(df_master[modality])
            updated_cases = df_master_updated[~pd.np.all(is_in_original, axis = 1)].index.tolist()
            if not pd.np.all(is_in_original):
                if 'Time_Last_Update' in df_master.columns:
                    is_original_row = pd.np.all(is_in_original.ix[df_master.index], axis = 1)
                    df_master_updated.loc[is_original_row, 'Time_Last_Update'] = df_master[is_original_row]['Time_Last_Update']
                else:
                    df_master_updated['Time_Last_Update'] = dt.now().strftime('%Y/%m/%d %H:%M:%S')
                    
                for case in updated_cases:
                    if case in df_master.index.tolist():
                        print df_master.ix[case].values, '->', df_master_updated.ix[case].values
                    else:
                        print "New case %s added." % case

                print 
                print
                
                if not args.is_dry_run:
                    df_master_updated[ordered_cols].to_csv(args.master, float_format = '%d')
                    print "The following subjects are updated."
                else:
                    print "The following subjects would be updated."
                print updated_cases
            else:
                print "No updates."
        else:
            if not args.is_dry_run:
                odir, tail = os.path.split(args.master)
                try:
                    os.makedirs(odir)
                except:
                    pass
                df_master_new.to_csv(args.master, float_format = '%d')
            
    if args.odir is not None and args.master is not None and not no_master:
        print "Rename updated Niftis"
        rename_nifti(df.ix[updated_cases], args.odir, dry_run = args.is_dry_run, cols = modality)
    elif args.odir is not None and (args.master is None or no_master):
        print "Rename all Niftis"
        rename_nifti(df, args.odir, dry_run = args.is_dry_run, cols = modality)        
    
    return 0

    
def rename_nifti(df, basedir, dry_run = True, 
                 cols = ['T1', 'T2', 'FLAIR', 'DTI', 'PCASL', 'RESTING', 'BOLD_BREATHHOLD']):
                        
    import pandas as pd
    from glob import glob
    
    for ID in df.index:
        print ID
        if 'pid' in df.columns:
            subj_id = df.ix[ID]['pid']
        else:
            subj_id = '-'.join(ID.split('-')[:-1])
        print "PID: %s" % subj_id
        odir = os.path.join(basedir, subj_id, ID)

        for mod in cols:
            old_links = glob(os.path.join(odir, '*%s*' % mod))
            if old_links:
                if not dry_run:
                    print "Removing old softlinks"
                    print old_links
                    map(os.unlink, old_links)
                else:
                    print "Will remove old softlinks"
                    print old_links
            print
        
            new_files = [(None, None)]
            if not pd.isnull(df.at[ID, mod]):
                
                orig_files = df.at[ID, mod].split(' ')
                prefix = '%s_%s' % (ID, mod)
                
                if len(orig_files) > 1:
                    new_files = [(f, os.path.join(odir, "%s_%s.nii.gz" % (prefix, str(i+1)))) for i, f in enumerate(orig_files)]
                elif len(orig_files) == 1:
                    new_files = [(orig_files[0], os.path.join(odir, "%s.nii.gz" % (prefix)))]
                else: # 0 image
                    continue
                    
                for f in new_files:
                    print("%s -> %s" % (f[0], f[1]))
                            
                if not dry_run:
                    try:
                        os.makedirs(odir)
                    except:
                        pass
                    
                    for f in new_files:
                        if os.path.islink(f[1]):
                            os.unlink(f[1])
                        os.symlink(f[0], f[1])
                    
                if mod == 'DTI':
                    # link bval & bvec too
                    bvals = [(f.replace('nii.gz','bval'), new_files[i][1].replace('nii.gz', 'bval'))
                              for i, f in enumerate(orig_files)]
                    bvecs = [(f.replace('nii.gz','bvec'), new_files[i][1].replace('nii.gz', 'bvec')) 
                              for i, f in enumerate(orig_files)]
                    for f in bvals + bvecs:
                        print("%s -> %s" % (f[0], f[1]))
                        if not dry_run:
                            if os.path.islink(f[1]):
                                os.unlink(f[1])
                            os.symlink(f[0], f[1])
#                        else:
#                            print("%s does not exist" % f[0])

        print 
        print

def create_master(df, cols = ['T1', 'T2', 'FLAIR', 'DTI', 'PCASL', 'RESTING', 'BOLD_BREATHHOLD']):
    import logger
    import pandas as pd
    from datetime import datetime as dt

    df_filecount = df.applymap(logger.count_files)
    full_id = df.index.tolist()
    subj_id_list = ['-'.join(i.split('-')[:-1]) for i in full_id]
    scan_date_list = [i.split('-')[-1] for i in full_id]
    df_master = df_filecount.copy()
    
    df_master.index.name = 'full_id'
    df_master['subj_id'] = subj_id_list
    df_master['scan_date'] = scan_date_list
    df_master['Exclude'] = pd.np.nan
    df_master['Notes'] = pd.np.nan
    df_master = df_master[['subj_id','scan_date'] + cols + ['Exclude','Notes']]
    df_master['Time_Last_Update'] = dt.now().strftime('%Y/%m/%d-%H:%M:%S')

    return df_master

if __name__ == '__main__':
    sys.exit(main())

