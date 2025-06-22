#!/usr/bin/env python
#
#   Run a set of files through a processing and decode chain, and handle the output.
#
#   Copyright (C) 2018  Mark Jessop <vk5qi@rfhead.net>
#   Released under GNU GPL v3 or later
#
#   Refer to the README.md in this directory for instructions on use.
#
import glob
import argparse
import os
import sys
import time
import traceback
import subprocess


# Dictionary of available processing types.

processing_type = {

    # Wenet, RS232 modulation
    # Convert to u8 using csdr, then pipe into fsk_demod, then drs232_ldpc.
    # Count bytes at the output as a metric of performance.
    'wenet_rs232_demod': {
        'demod': '| csdr convert_f_u8 | ../rx/fsk_demod --cu8 -s --stats=100 2 921416 115177 - - 2> stats.txt | ',
        'decode': '../rx/drs232_ldpc - - 2> /dev/null ',
        "post_process" : " |  wc -c", #
        'files' : "./generated/wenet_sample_fs921416*.bin"
    },
    'wenet_rs232_demod_c16': {
        'demod': '| csdr convert_f_s16 | ../rx/fsk_demod --cs16 -s --stats=100 2 921416 115177 - - 2> stats.txt | ',
        'decode': '../rx/drs232_ldpc - - 2> /dev/null ',
        "post_process" : " |  wc -c", #
        'files' : "./generated/wenet_sample_fs921416*.bin"
    },
}

def run_analysis(mode, file_mask=None, shift=0.0, verbose=False, log_output = None, dry_run = False, quick=False, show=False):


    _mode = processing_type[mode]

    # If we are not supplied with a file mask, use the defaults.
    if file_mask is None:
        file_mask = _mode['files']

    # Get the list of files.
    _file_list = glob.glob(file_mask)
    if len(_file_list) == 0:
        print("No files found matching supplied path.")
        return

    # Sort the list of files.
    _file_list.sort()

    # If we are only running a quick test, just process the last file in the list.
    if quick:
        _file_list = [_file_list[-1]]

    _first = True

    # Calculate the frequency offset to apply, if defined.
    _shiftcmd = "| csdr shift_addition_cc %.5f 2>/dev/null" % (shift/96000.0)

    if log_output is not None:
        _log = open(log_output,'w')

    # Iterate over the files in the supplied list.
    for _file in _file_list:

        # Generate the command to run.
        _cmd = "cat %s "%_file 

        # Add in an optional frequency error if supplied.
        if shift != 0.0:
            _cmd += _shiftcmd

        # Add on the rest of the demodulation and decoding commands.
        _cmd += _mode['demod'] + _mode['decode'] 
        
        if args.show:
            _cmd += " | head -n 10"
        else:
            _cmd += _mode['post_process']


        if _first or dry_run:
            print("Command: %s" % _cmd)
            _first = False

        if dry_run:
            continue

        # Run the command.
        try:
            _start = time.time()
            _output = subprocess.check_output(_cmd, shell=True, stderr=None)
            _output = _output.decode()
        except:
            #traceback.print_exc()
            _output = "error"

        _runtime = time.time() - _start

        _result = "%s, %s, %.3f" % (os.path.basename(_file), _output.strip(), _runtime)

        print(_result)
        if log_output is not None:
            _log.write(_result + '\n')

        if verbose:
            print("Runtime: %.1d" % _runtime)

    if log_output is not None:
        _log.close()




if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--mode", type=str, default="rs41_fsk_demod_soft", help="Operation mode.")
    parser.add_argument("-f", "--files", type=str, default=None, help="Glob-path to files to run over.")
    parser.add_argument("-v", "--verbose", action='store_true', default=False, help="Show additional debug info.")
    parser.add_argument("-d", "--dry-run", action='store_true', default=False, help="Show additional debug info.")
    parser.add_argument("--shift", type=float, default=0.0, help="Shift the signal-under test by x Hz. Default is 0.")
    parser.add_argument("--batch", action='store_true', default=False, help="Run all tests, write results to results directory.")
    parser.add_argument("--quick", action='store_true', default=False, help="Only process the last sample file in the list (usually the strongest). Useful for checking the demodulators are still working.")
    parser.add_argument("--show", action='store_true', default=False, help="Show the first few lines of output, instead of running the post-processing step.")
    args = parser.parse_args()

    # Check the mode is valid.
    if args.mode not in processing_type:
        print("Error - invalid operating mode.")
        print("Valid Modes: %s" % str(processing_type.keys()))
        sys.exit(1)


    batch_modes = []

    if args.batch:
        for _mode in batch_modes:
            _log_name = "./results/" + _mode + ".txt"
            run_analysis(_mode, file_mask=None, shift=args.shift, verbose=args.verbose, log_output=_log_name, dry_run=args.dry_run, quick=args.quick, show=args.show)
    else:
        run_analysis(args.mode, args.files, shift=args.shift, verbose=args.verbose, dry_run=args.dry_run, quick=args.quick, show=args.show)
