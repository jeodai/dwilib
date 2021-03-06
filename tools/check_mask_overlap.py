#!/usr/bin/python

"""Check if there are voxels in the 'other' mask (e.g. lesion) that don't
overlap the 'container' mask (e.g. prostate).
"""

from __future__ import absolute_import, division, print_function
import argparse

import numpy as np
import matplotlib.pyplot as plt

import dwi.files
import dwi.util


def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('container',
                   help='container mask (e.g. prostate)')
    p.add_argument('other',
                   help='other mask (e.g. lesion)')
    p.add_argument('--verbose', '-v', action='count',
                   help='increase verbosity')
    p.add_argument('--fig',
                   help='output figure')
    return p.parse_args()


def read_mask(path):
    """Read pmap as a mask."""
    mask, _ = dwi.files.read_pmap(path)
    assert mask.ndim == 4, mask.ndim
    assert mask.shape[-1] == 1, mask.shape
    mask = mask[..., 0].astype(np.bool).astype(np.int8)
    return mask


def get_overlap(container, other):
    """Get overlap array."""
    overlap = np.zeros_like(container, dtype=np.int8)
    overlap[container == 1] = 1  # Set container voxels.
    overlap[other == 1] = 3  # Set other voxels.
    overlap[container - other == -1] = 2  # Set non-container other voxels.
    return overlap


def write_figure(overlap, path):
    overlap = overlap.astype(np.float16) / 3
    plt.rcParams['image.aspect'] = 'equal'
    plt.rcParams['image.cmap'] = 'jet'
    plt.rcParams['image.interpolation'] = 'none'
    n_cols = 4
    n_rows = np.ceil(len(overlap) / n_cols)
    fig = plt.figure(figsize=(n_cols*6, n_rows*6))
    for i, a in enumerate(overlap):
        ax = fig.add_subplot(n_rows, n_cols, i+1)
        ax.set_title('Slice {}'.format(i))
        plt.imshow(a, vmin=0, vmax=1)
    plt.tight_layout()
    print('Writing figure:', path)
    plt.savefig(path, bbox_inches='tight')
    plt.close()


def main():
    args = parse_args()
    container = read_mask(args.container)
    other = read_mask(args.other)
    assert container.shape == other.shape, (container.shape, other.shape)
    overlap = get_overlap(container, other)
    n = np.count_nonzero(overlap == 2)
    if n:
        s = '{c}, {o}: {n} voxels outside container'
        print(s.format(c=args.container, o=args.other, n=n))
    if args.fig:
        write_figure(overlap, args.fig)


if __name__ == '__main__':
    main()
