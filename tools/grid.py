#!/usr/bin/env python2

"""Get grid-wise features."""

from __future__ import absolute_import, division, print_function
import argparse
from itertools import product

import numpy as np
import scipy.ndimage
import scipy.stats

import dwi.files
import dwi.util


def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
                   help='increase verbosity')
    p.add_argument('--image', required=True,
                   help='input image or pmap')
    p.add_argument('--prostate', metavar='MASKFILE', required=True,
                   help='prostate mask')
    p.add_argument('--lesions', metavar='MASKFILE', nargs='+', required=True,
                   help='lesion masks')
    p.add_argument('--winsize', type=float, default=5,
                   help='window (cube) size in millimeters (default 5)')
    p.add_argument('--voxelsize', type=float,
                   help='rescaled voxel size in millimeters (try 0.25)')
    p.add_argument('--output', metavar='FILENAME', required=True,
                   help='output ASCII file')
    return p.parse_args()


def read_mask(path, expected_voxel_spacing):
    """Read pmap as a mask."""
    img, attrs = dwi.files.read_pmap(path)
    img = img[..., 0].astype(np.bool)
    voxel_spacing = attrs['voxel_spacing']
    if voxel_spacing != expected_voxel_spacing:
        raise ValueError('Expected voxel spacing {}, got {}'.format(
            expected_voxel_spacing, voxel_spacing))
    return img


def unify_masks(masks):
    """Unify a sequence of masks into one."""
    # return np.sum(masks, axis=0, dtype=np.bool)
    return reduce(np.maximum, masks)


def get_mbb(mask, voxel_spacing, pad):
    """Get mask minimum bounding box as slices, with minimum padding in mm."""
    padding = tuple(int(np.ceil(pad / x)) for x in voxel_spacing)
    physical_padding = tuple(x * y for x, y in zip(padding, voxel_spacing))
    mbb = dwi.util.bounding_box(mask, padding)
    slices = tuple(slice(*x) for x in mbb)
    print('Cropping minimum bounding box with pad:', pad)
    print('\tVoxel padding:', padding)
    print('\tPhysical padding:', physical_padding)
    print('\tMinimum bounding box:', mbb)
    return slices


def rescale(img, src_voxel_spacing, dst_voxel_spacing):
    """Rescale image according to voxel spacing sequences (mm per voxel)."""
    factor = tuple(s/d for s, d in zip(src_voxel_spacing, dst_voxel_spacing))
    print('Scaling:', src_voxel_spacing, dst_voxel_spacing, factor)
    output = scipy.ndimage.interpolation.zoom(img, factor, order=0)
    return output


def float2bool_mask(a):
    """Convert float array to boolean mask (round, clip to [0, 1])."""
    a = a.round()
    a.clip(0, 1, out=a)
    a = a.astype(np.bool)
    return a


def generate_windows(imageshape, winshape, center):
    """Generate slice objects for a grid of windows around given center.

    Float center will be rounded.
    """
    center = tuple(int(round(x)) for x in center)
    starts = [i % w for i, w in zip(center, winshape)]
    stops = [i-w+1 for i, w in zip(imageshape, winshape)]
    its = (xrange(*x) for x in zip(starts, stops, winshape))
    for coords in product(*its):
        slices = tuple(slice(i, i+w) for i, w in zip(coords, winshape))
        yield slices


def get_datapoint(image, prostate, lesion):
    """Extract output datapoint for a cube.

    The cube window is included if at least half of it is of prostate.
    """
    assert image.shape == prostate.shape == lesion.shape
    # At least half of the window must be of prostate.
    if np.count_nonzero(prostate) / prostate.size >= 0.5:
        return [
            (np.count_nonzero(lesion) > 0),
            np.nanmean(image),
            np.nanmedian(image),
        ]
    return None


def print_correlations(data, params):
    """Print correlations for testing."""
    data = np.asarray(data)
    print(data.shape, data.dtype)
    indices = range(data.shape[-1])
    for i, j in product(indices, indices):
        if i < j:
            rho, pvalue = scipy.stats.spearmanr(data[:, i], data[:, j])
            s = 'Spearman: {:8} {:8} {:+1.4f} {:+1.4f}'
            print(s.format(params[i], params[j], rho, pvalue))


def main():
    args = parse_args()
    image, attrs = dwi.files.read_pmap(args.image)
    voxel_spacing = attrs['voxel_spacing']
    image = image[..., 0]
    prostate = read_mask(args.prostate, voxel_spacing)
    lesion = unify_masks([read_mask(x, voxel_spacing) for x in args.lesions])
    image[-prostate] = np.nan  # XXX: Is it ok to set background as nan?
    print('Lesions:', len(args.lesions))
    assert image.shape == prostate.shape == lesion.shape

    physical_size = tuple(x*y for x, y in zip(image.shape, voxel_spacing))
    centroid = dwi.util.centroid(prostate)
    print('Image:', image.shape, image.dtype)
    print('\tVoxel spacing:', voxel_spacing)
    print('\tPhysical size:', physical_size)
    print('\tProstate centroid:', centroid)

    # Crop MBB.
    slices = get_mbb(prostate, voxel_spacing, 15)
    image = image[slices]
    prostate = prostate[slices]
    lesion = lesion[slices]
    assert image.shape == prostate.shape == lesion.shape

    # Rescale image and masks.
    if args.voxelsize is not None:
        src_voxel_spacing = voxel_spacing
        voxel_spacing = (args.voxelsize,) * 3
        image = rescale(image, src_voxel_spacing, voxel_spacing)
        prostate = prostate.astype(np.float_)
        prostate = rescale(prostate, src_voxel_spacing, voxel_spacing)
        prostate = float2bool_mask(prostate)
        lesion = lesion.astype(np.float_)
        lesion = rescale(lesion, src_voxel_spacing, voxel_spacing)
        lesion = float2bool_mask(lesion)
        assert image.shape == prostate.shape == lesion.shape

    physical_size = tuple(x*y for x, y in zip(image.shape, voxel_spacing))
    centroid = dwi.util.centroid(prostate)
    print('Image:', image.shape, image.dtype)
    print('\tVoxel spacing:', voxel_spacing)
    print('\tPhysical size:', physical_size)
    print('\tProstate centroid:', centroid)

    # Extract grid datapoints.
    metric_winshape = (args.winsize,) * 3
    voxel_winshape = tuple(int(round(x/y)) for x, y in zip(metric_winshape,
                                                           voxel_spacing))
    print('Window shape (metric, voxel):', metric_winshape, voxel_winshape)
    windows = generate_windows(image.shape, voxel_winshape, centroid)
    data = [get_datapoint(image[x], prostate[x], lesion[x]) for x in windows]
    data = [x for x in data if x is not None]
    params = 'lesion mean median'.split()
    print_correlations(data, params)

    # Write output.
    attrs = dict(parameters=params, n_lesions=len(args.lesions))
    dwi.files.write_pmap(args.output, data, attrs)


if __name__ == '__main__':
    main()
