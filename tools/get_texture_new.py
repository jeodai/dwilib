#!/usr/bin/env python2

"""Calculate texture properties for a masked area."""

# TODO: pmap normalization for GLCM

from __future__ import absolute_import, division, print_function
import argparse
import collections

import numpy as np

import dwi.dataset
import dwi.mask
import dwi.standardize
import dwi.texture
import dwi.util


def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
                   help='increase verbosity')
    p.add_argument('--pmapdir', default='results_Mono_combinedDICOM',
                   help='input parametric map directory')
    p.add_argument('--param', default='ADCm',
                   help='image parameter to use')
    p.add_argument('--case', type=int,
                   help='case number')
    p.add_argument('--scan',
                   help='scan identifier')
    p.add_argument('--mask',
                   help='mask file to use')
    p.add_argument('--std',
                   help='standardization file to use')
    p.add_argument('--method', metavar='METHOD',
                   help='method')
    p.add_argument('--slices', default='maxfirst',
                   help='slice selection (maxfirst, max, all)')
    p.add_argument('--winspec', default='5',
                   help='window specification (side length, all, mbb)')
    p.add_argument('--portion', type=float, required=False, default=0,
                   help='portion of selected voxels required for each window')
    p.add_argument('--voxel', choices=('all', 'mean'), default='all',
                   help='voxel to output (all, mean)')
    p.add_argument('--output', metavar='FILENAME',
                   help='output ASCII file')
    return p.parse_args()


def max_mask(mask, winsize):
    """Return a mask that has the voxels selected that have the maximum number
    of surrounding voxels selected in the original mask.
    """
    d = collections.defaultdict(list)
    for pos, win in dwi.util.sliding_window(mask, winsize, mask=mask):
        d[np.count_nonzero(win)].append(pos)
    r = np.zeros_like(mask)
    for pos in d[max(d)]:
        r[pos] = True
    return r


def portion_mask(mask, winsize, portion=1., resort_to_max=True):
    """Return a mask that selects (only) voxels that have the window at each
    selected voxel origin up to a minimum portion in the original mask selected
    (1 means the whole window must be selected, 0 gives the original mask).

    If resort_to_max is true, the window with maximum number of selected voxels
    is used in case the resulting mask would otherwise be empty.
    """
    r = np.zeros_like(mask)
    for pos, win in dwi.util.sliding_window(mask, winsize, mask=mask):
        if np.count_nonzero(win) / win.size >= portion:
            r[pos] = True
    if resort_to_max and np.count_nonzero(r) == 0:
        r = max_mask(mask, winsize)
    return r


def main():
    args = parse_args()
    if args.verbose:
        print('Reading data...')
    data = dwi.dataset.dataset_read_samples([(args.case, args.scan)])
    dwi.dataset.dataset_read_pmaps(data, args.pmapdir, [args.param])
    img = data[0]['image'].squeeze()

    if args.mask is not None:
        mask = dwi.mask.read_mask(args.mask)
        if isinstance(mask, dwi.mask.Mask):
            mask = mask.convert_to_3d(img.shape[0])
    else:
        # A default mask for testing.
        mask = dwi.mask.Mask3D(np.zeros_like(img, dtype=bool))
        # mask.array[9:-9, 50:-50, 50:-50] = True
        tuples = dwi.util.bounding_box(img)
        print('Using minimum bounding box as mask: {}'.format(tuples))
        slices = [slice(*t) for t in tuples]
        mask.array[slices] = True

    if img.shape != mask.shape():
        raise Exception('Image shape {} does not match mask shape {}'.format(
            img.shape, mask.shape()))
    if mask.n_selected() == 0:
        raise ValueError('Empty mask.')

    if args.slices == 'maxfirst':
        slice_indices = [mask.max_slices()[0]]
    elif args.slices == 'max':
        slice_indices = mask.max_slices()
    elif args.slices == 'all':
        slice_indices = mask.selected_slices()
    else:
        raise Exception('Invalid slice set specification', args.slices)

    # Zero other slices in mask.
    for i in range(len(mask.array)):
        if i not in slice_indices:
            mask.array[i] = 0

    # Get portion mask.
    if args.winspec in ('all', 'mbb'):
        pmask = mask.array  # Some methods don't use window.
    elif args.winspec.isdigit():
        winsize = int(args.winspec)
        assert winsize > 0
        winshape = (1, winsize, winsize)
        pmask = portion_mask(mask.array, winshape, args.portion)
    else:
        raise ValueError('Invalid window spec: {}'.format(args.winspec))

    if args.verbose:
        print('Image: {s}, slice: {i}, voxels: {n}, window: {w}'.format(
            s=img.shape, i=slice_indices, n=np.count_nonzero(mask.array),
            w=args.winspec))

    if args.std:
        if args.verbose:
            print('Standardizing...')
        # img[slice_indices] = dwi.standardize.standardize(img[slice_indices],
        #                                                  args.std)
        img = dwi.standardize.standardize(img, args.std)

    if args.verbose:
        print('Calculating {} texture features...'.format(args.method))
    avg = (args.voxel == 'mean')
    tmap, names = dwi.texture.get_texture(img, args.method, args.winspec,
                                          mask=pmask, avg=avg)

    if args.verbose:
        print('Writing shape {s} to {o}'.format(s=tmap.shape, o=args.output))
    # tmap = np.array(tmap, dtype=np.float32)
    dwi.files.write_pmap(args.output, tmap, names)


if __name__ == '__main__':
    main()
