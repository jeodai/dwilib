#!/usr/bin/env python2

"""Draw some texture maps with focus on lesions."""

# This is for the MedPhys texturepaper.

from __future__ import absolute_import, division, print_function
import argparse
from collections import namedtuple
import logging
import os.path
import re

import numpy as np

import dwi.files
import dwi.mask
import dwi.paths
import dwi.plot
import dwi.util


def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
                   help='be more verbose')
    p.add_argument('--featlist', '-f', default='feats.txt')
    p.add_argument('--samplelist', '-s', default='all')
    p.add_argument('--outdir', '-o', default='figs')
    return p.parse_args()


def show_image(plt, image, colorbar=True, scale=None, **kwargs):
    """Show image."""
    d = {}
    if scale is not None:
        d['vmin'], d['vmax'] = scale
    d.update(kwargs)
    im = plt.imshow(image, **d)
    if colorbar:
        dwi.plot.add_colorbar(im, pad_fraction=0)


def show_outline(plt, mask):
    """Show outline."""
    view = np.full_like(mask, np.nan, dtype=np.float16)
    view = dwi.mask.border(mask, out=view)
    cmap = 'coolwarm'
    d = dict(cmap=cmap, interpolation='nearest', vmin=0, vmax=1, alpha=1.0)
    plt.imshow(view, **d)


def get_lesion_mask(masks, slice_index=None):
    """Get unified single-slice lesion mask and index to most relevan slice."""
    def max_slices(mask):
        """Return indices of maximum slices."""
        counts = [np.count_nonzero(x) for x in mask]
        maxcount = max(counts)
        return [i for i, c in enumerate(counts) if c == maxcount]

    # Use slice with maximum lesion volume.
    mask = dwi.util.unify_masks(masks)
    centroids = [int(round(np.mean(max_slices(x)))) for x in masks]
    centroid = int(round(np.mean(max_slices(mask))))

    # centroids = [int(round(dwi.util.centroid(x)[0])) for x in masks]
    # centroid = int(round(dwi.util.centroid(mask)[0]))

    logging.debug('Lesion centroids (total): %s (%s)', centroids, centroid)
    logging.info('Mask shape: %s, centroid: %i, slice: %s', mask.shape,
                 centroid, slice_index)
    if slice_index is None:
        slice_index = centroid
    mask = mask[slice_index]

    return mask, slice_index


def read_lmask(mode, case, scan):
    mode = dwi.util.ImageMode(mode)
    paths = []
    try:
        for i in range(1, 4):
            paths.append(dwi.paths.mask_path(mode, 'lesion', case, scan, i))
    except IOError:
        pass
    masks = [dwi.files.read_mask(x) for x in paths]

    # Manually override slice index.
    slice_indices = {
        (64, '1a', 'T2w-std'): 7,
        (64, '1a', 'T2-fitted'): 5,
        }

    slice_index = slice_indices.get((case, scan, str(mode)))
    lmask, img_slice = get_lesion_mask(masks, slice_index=slice_index)
    return lmask, img_slice


def read_pmap(mode, case, scan, img_slice):
    mode = dwi.util.ImageMode(mode)
    path = dwi.paths.pmap_path(mode, case, scan)
    pmap, _ = dwi.files.read_pmap(path, ondisk=True, params=[0])
    pmap = pmap[img_slice, :, :, 0]
    pmap = dwi.util.normalize(pmap, mode)
    return pmap


def read_tmap(mode, case, scan, img_slice, texture_spec):
    mode = dwi.util.ImageMode(mode)
    tmap = dwi.paths.texture_path(mode, case, scan, None, 'prostate', 'all', 0,
                                  texture_spec.method, texture_spec.winsize,
                                  voxel='all')
    param = '{winsize}-{method}({feature})'.format(**texture_spec._asdict())
    tmap, attrs = dwi.files.read_pmap(tmap, ondisk=True, params=[param])
    tscale = tuple(np.nanpercentile(tmap[:, :, :, 0], (1, 99)))
    tmap = tmap[img_slice, :, :, 0]
    assert param == attrs['parameters'][0]
    return tmap, param, tscale


def read_histology(case):
    """Read histology section image."""
    from glob import glob
    import PIL
    pattern = '/mri/pink_images/extracted/{}-*'.format(case)
    paths = glob(pattern)
    if not paths:
        raise IOError('Histology image not found: {}'.format(pattern))
    images = [np.array(PIL.Image.open(x)) for x in sorted(paths)]
    # If several, concatenate by common width.
    min_width = min(x.shape[1] for x in images)
    images = [x[:, 0:min_width, :] for x in images]
    image = np.concatenate(images)
    return image


def rescale(image, factor, order=0):
    """Rescale."""
    from scipy.ndimage import interpolation
    return interpolation.zoom(image, factor, order=order)


def rescale_as_float(image, factor):
    """Convert to float, rescale, convert back. Special boolean handling."""
    from scipy.ndimage import interpolation
    typ = image.dtype
    image = image.astype(np.float)
    image = interpolation.zoom(image, factor)
    if typ == np.bool:
        image = dwi.util.asbool(image)
    else:
        image = image.astype(typ)
    return image


def read(mode, case, scan, texture_spec):
    """Read files."""
    try:
        histology = read_histology(case)
    except IOError:
        # histology = np.eye(5)
        raise

    lmask, img_slice = read_lmask(mode, case, scan)
    pmap = read_pmap(mode, case, scan, img_slice)
    tmap, param, tscale = read_tmap(mode, case, scan, img_slice, texture_spec)

    bb = dwi.util.bbox(np.isfinite(tmap), 10)
    pmap = pmap[bb]
    tmap = tmap[bb]
    lmask = lmask[bb]

    if mode.startswith('DWI'):
        pmap = rescale(pmap, 2)
        tmap = rescale(tmap, 2)
        lmask = rescale_as_float(lmask, 2)

    lmask[np.isnan(tmap)] = False  # Remove lesion voxels outside prostate.
    pmap_prostate = np.where(np.isfinite(tmap), pmap, np.nan)
    tmap_lesion = np.where(lmask, tmap, np.nan)
    pmask = np.isfinite(tmap)

    images = dict(pmap=pmap, tmap=tmap, lmask=lmask,
                  pmap_prostate=pmap_prostate, tmap_lesion=tmap_lesion,
                  pmask=pmask)
    assert len(set(x.shape for x in images.values())) == 1
    images['histology'] = histology
    images['tscale'] = tscale
    return images, param


def plot(images, title, path):
    """Plot."""
    pscale = (0, 1)
    # tscale = tuple(np.nanpercentile(images['tmap'], (1, 99)))
    tscale = images['tscale']
    def histology_image(plt):
        plt.imshow(images['histology'])
        # plt.title('histology section')
    def pmap(plt):
        show_image(plt, images['pmap'], scale=pscale, cmap='gray')
    def prostate_pmap(plt):
        show_image(plt, images['pmap_prostate'], scale=pscale, cmap='gray')
        show_outline(plt, images['lmask'])
    def prostate_texture(plt):
        show_image(plt, images['tmap'], scale=tscale)
        show_outline(plt, images['lmask'])
    def lesion_texture(plt):
        # show_image(plt, images['tmap_lesion'], scale=tscale)
        show_image(plt, images['tmap_lesion'])
    funcs = [histology_image, prostate_pmap, prostate_texture, lesion_texture]
    it = dwi.plot.generate_plots(ncols=len(funcs), suptitle=title, path=path)
    for i, plt in enumerate(it):
        dwi.plot.noticks(plt)
        f = funcs[i]
        # plt.title(f.__name__.replace('_', ' '))
        plt.title('')
        f(plt)


def cases_scans_lesions(mode, samplelist):
    mode = dwi.util.ImageMode(mode)
    path = dwi.paths.samplelist_path(mode, samplelist)
    patients = dwi.files.read_patients_file(path)
    for p in patients:
        for scan in p.scans:
            yield p.num, scan, p.lesions


def main():
    """Main."""
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    TextureSpec = namedtuple('TextureSpec', ['winsize', 'method', 'feature'])
    blacklist = [21, 22, 27, 42, 74, 79]
    whitelist = [23, 24, 26, 29, 64]

    for i, line in enumerate(dwi.files.valid_lines(args.featlist)):
        words = line.split()
        mode = words[0]
        texture_spec = TextureSpec(*words[1:])
        print(i, mode, texture_spec)
        for c, s, l in cases_scans_lesions(mode, args.samplelist):
            # if c not in [64]:
            #     continue
            if blacklist and c in blacklist:
                continue
            if whitelist and c not in whitelist:
                continue
            if len(l) < 2:
                continue
            if all(x.score == l[0].score for x in l):
                continue
            try:
                images, param = read(mode, c, s, texture_spec)
            except IOError as e:
                logging.error(e)
                continue
            scores = '/'.join(str(x.score) for x in l)
            locations = '/'.join(str(x.location) for x in l)
            param = re.sub(r'^([0-9]-)', r'0\1', param)  # Two-digit winsize.
            title = '{}, {}-{}, {}, {}, {}'.format(mode, c, s, scores,
                                                   locations, param)
            # d = dict(o=args.outdir, m=mode, p=param, c=c, s=s)
            # path = '{o}/{c:03}-{s}_{m}_{p}.png'.format(**d)
            d = dict(m=mode, c=c, s=s, tw=int(texture_spec.winsize),
                     tm=texture_spec.method, tf=texture_spec.feature)
            filename = ('{c:03}-{s}_{m}_{tm}({tf})-{tw:02}.png').format(**d)
            plot(images, title, os.path.join(args.outdir, filename))


if __name__ == '__main__':
    main()
