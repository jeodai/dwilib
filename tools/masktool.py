#!/usr/bin/env python2

"""Mask tool."""

import argparse
import numpy as np

import dwi.mask
import dwi.util

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description = __doc__)
    p.add_argument('-v', '--verbose', action='count',
            help='increase verbosity')
    p.add_argument('--input', '-i', metavar='INFILE', required=True,
            help='input mask file')
    p.add_argument('--subregion', '-s', metavar='OUTFILE',
            help='output subregion file')
    args = p.parse_args()
    return args

args = parse_args()
mask = dwi.mask.read_mask(args.input)

print mask
print mask.bounding_box()
print mask.n_selected()
print mask.selected_slices()

if args.subregion:
    bb = mask.bounding_box(pad=(np.inf, 10, 10))
    if args.verbose:
        print 'Writing subregion to %s...' % args.subregion
    dwi.util.write_subregion_file(args.subregion, bb)