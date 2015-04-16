#!/usr/bin/env python2

"""Calculate texture properties for a ROI."""

import argparse
import glob
import re
import numpy as np

import dwi.asciifile
import dwi.dataset
import dwi.mask
import dwi.plot
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
    p.add_argument('--methods', metavar='METHOD', nargs='+',
            default=['all'],
            help='methods separated by comma')
    p.add_argument('--output', metavar='FILENAME',
            help='output ASCII file')
    args = p.parse_args()
    return args

def normalize(pmap):
    """Normalize images within given range and convert to byte maps."""
    import skimage
    import skimage.exposure
    #in_range = (0, 0.03)
    in_range = (0, 0.005)
    #in_range = (0, 0.002)
    #in_range = (pmap.min(), pmap.max())
    pmap = skimage.exposure.rescale_intensity(pmap, in_range=in_range)
    pmap = skimage.img_as_ubyte(pmap)
    return pmap

def clip(pmap):
    """Clip ADC pmap slice."""
    assert pmap.ndim == 2
    r = pmap.copy()
    r.shape += (1,)
    dwi.util.clip_pmap(r, ['ADCm'])
    r.shape = r.shape[:-1]
    return r


args = parse_args()
print 'Reading data...'
data = dwi.dataset.dataset_read_samples([(args.case, args.scan)])
dwi.dataset.dataset_read_pmaps(data, args.pmapdir, [args.param])
mask = dwi.mask.read_mask(args.mask)

img = data[0]['image']
if isinstance(mask, dwi.mask.Mask):
    mask = mask.convert_to_3d(img.shape[0])

img_slice = mask.selected_slice(img)[:,:,0]
mask_slice = mask.array[mask.selected_slices()[0]]
roi = mask.selected(img)
roi.shape = dwi.util.make2d(roi.size)
assert roi.shape[0] == roi.shape[1]
winsize = roi.shape[0]
sl = slice(winsize//2, -(winsize//2))
if args.verbose > 1:
    print 'Image: %s, ROI: %s' % (img.shape, roi.shape)

propnames = []
props = []

if 'basic' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.stats_map(img_slice, winsize, mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'glcm' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.glcm_map(normalize(img_slice), winsize, mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'haralick' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.haralick_map(normalize(img_slice), winsize,
            mask=mask_slice)
    for i, (a, n) in enumerate(zip(tmap, names)):
        if ' ' in n:
            n = ''.join([word[0] for word in n.split()])
        props.append(np.mean(a[mask_slice]))
        propnames.append('haralick{:d}-{:s}'.format(i+1, n))

if 'lbp' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.lbp_freq_map(img_slice, winsize)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'hog' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.hog_map(img_slice, winsize, mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'gabor' in args.methods or 'all' in args.methods:
    # TODO only for ADCm, clips them
    tmap, names = dwi.texture.gabor_map(clip(img_slice), winsize,
            mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'moment' in args.methods or 'all' in args.methods:
    tmap, names = dwi.texture.moment_map(img_slice, winsize, max_order=12,
            mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if 'haar' in args.methods or 'all' in args.methods:
    #l = [0,1,3,4] # Exclude middle row and column.
    #roi_corners = roi[l][:,l]
    #d = dwi.texture.haar_features(roi_corners)
    #for k, v in d.iteritems():
    #    propnames.append('haar{}'.format(str(k)).translate(None, " '"))
    #    props.append(v)
    tmap, names = dwi.texture.haar_map(img_slice, winsize, mask=mask_slice)
    for a, n in zip(tmap, names):
        props.append(np.mean(a[mask_slice]))
        propnames.append(n)

if args.verbose:
    print 'Writing %s features to %s' % (len(props), args.output)
dwi.asciifile.write_ascii_file(args.output, [props], propnames)

#roi = roi[50:150, 50:150]
#lbp_data, lbp_freq_data, patterns = dwi.texture.lbp_freqs(roi)
#freqs = np.rollaxis(lbp_freq_data, 2)
#dwi.plot.show_images([[roi, lbp_data], freqs[:5], freqs[5:]])
