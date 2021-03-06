#!/usr/bin/python

"""Ad-hoc script to call pcorr.py. The grid data should be restructured."""

from __future__ import absolute_import, division, print_function
import argparse
from itertools import product
import os


def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
                   help='be more verbose')
    p.add_argument('directory',
                   help='input directory')
    return p.parse_args()


def do_method(directory, lesion_thresholds, name, winspecs, nfeats):
    for l, w, f in product(lesion_thresholds, winspecs, range(nfeats)):
        do_feat(directory, l, name, w, f)


def do_feat(directory, lesion_threshold, name, winspec, feat):
    prostate_threshold = 0.5
    if winspec is None:
        path = '{d}/{n}/*-*-{f}.txt'
    else:
        path = '{d}/{n}-{w}/*-*-{f}.txt'
    path = path.format(d=directory, n=name, w=winspec, f=feat)
    cmd = 'pcorr.py --thresholds {pt} {lt} {path}'
    cmd = cmd.format(pt=prostate_threshold, lt=lesion_threshold, path=path)
    exit_status = os.system(cmd)
    assert exit_status == 0, (cmd, exit_status)
    return exit_status


def main():
    args = parse_args()
    lesion_thresholds = [x/10 for x in range(1, 10)]
    if 'DWI' in args.directory:
        rng = range(3, 16, 2)
    elif 'T2' in args.directory:
        rng = range(3, 30, 4)
    else:
        raise Exception('Unknown input')
    methods = [
        ('gabor', rng, 48),
        ('glcm', rng, 30),
        # ('glcm_mbb', ['mbb'], 30),
        ('haar', rng, 24),
        # ('hog', rng, 1),
        ('hu', rng, 7),
        ('lbp', rng, 10),
        ('raw', [None], 1),
        # ('sobel', [3], 2),
        # ('stats_all', ['all'], 19),
        # ('zernike', rng, 25),
    ]
    for method in methods:
        do_method(args.directory, lesion_thresholds, *method)


if __name__ == '__main__':
    main()
