#!/usr/bin/env python2

"""Find most interesting ROI's in a DWI image."""

import os.path
import sys
import argparse

import numpy as np

from dwi import asciifile
from dwi import fit
from dwi import util

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description = __doc__)
    p.add_argument('-v', '--verbose',
            action='count',
            help='increase verbosity')
    p.add_argument('-d', '--dim', metavar='I',
            nargs=3, type=int, default=[1,5,5],
            help='dimensions of wanted ROI (3 integers; default 1 5 5)')
    p.add_argument('-i', '--input',
            required=True,
            help='input parametric map file')
    p.add_argument('-m', '--inmask',
            help='input mask file')
    p.add_argument('-o', '--output',
            help='output mask file')
    p.add_argument('-g', '--graphic',
            help='output graphic file')
    args = p.parse_args()
    return args

def get_score_param(img, param):
    """Return parameter score of given ROI."""
    if param.startswith('ADC'):
        #r = 1-np.mean(img)
        r = 1./(np.mean(img)-0.0008)
        if np.min(img) < 0.0002:
            r = 0
    elif param.startswith('K'):
        r = np.mean(img)/1000
    elif param.startswith('score'):
        r = np.mean(img)
    else:
        r = 0 # Unknown parameter
    return r

def get_score(img, params):
    """Return total score of given ROI."""
    scores = [get_score_param(i, p) for i, p in zip(img.T, params)]
    r = sum(scores)
    return r

def get_roi_scores(img, d, params):
    """Return array of all scores for each possible ROI of given dimension."""
    scores_shape = tuple((img.shape[i]-d[i]+1 for i in range(3)))
    scores = np.zeros(scores_shape)
    scores.fill(np.nan)
    for i in range(scores.shape[0]):
        for j in range(scores.shape[1]):
            for k in range(scores.shape[2]):
                z = (i, i+d[0])
                y = (j, j+d[1])
                x = (k, k+d[2])
                roi = img[z[0]:z[1], y[0]:y[1], x[0]:x[1], :]
                scores[i,j,k] = get_score(roi, params)
    return scores

def get_scoremap(img, d, params, n_rois):
    """Return array like original image, with scores of n_rois best ROI's."""
    scores = get_roi_scores(img, d, params)
    #print np.unravel_index(scores.argmax(), scores.shape)
    indices = scores.ravel().argsort()[::-1] # Sort ROI's by descending score.
    indices = indices[0:n_rois] # Select best ones.
    indices = [np.unravel_index(i, scores.shape) for i in indices]
    #scoremap = np.zeros_like(img[...,0])
    scoremap = np.zeros(img.shape[0:-1] + (1,))
    for z, y, x in indices:
        scoremap[z:z+d[0], y:y+d[1], x:x+d[2], 0] += scores[z,y,x]
    return scoremap

def line_to_text(line):
    return ''.join(map(str, line))

def mask_to_text(mask):
    return '\n'.join(map(line_to_text, mask))


args = parse_args()

af = asciifile.AsciiFile(args.input)
img = af.a.view()
params = af.params()
img.shape = af.subwindow_shape() + (img.shape[-1],)

# Clip outliers.
for i in range(img.shape[-1]):
    if params[i].startswith('ADC'):
        img[...,i].clip(0, 0.002, out=img[...,i])
    elif params[i].startswith('K'):
        img[...,i].clip(0, 2, out=img[...,i])

#dims = [(1,1,1)]
dims = [(1,i,i) for i in range(5, 10)]
#n_rois = 2000
n_rois = 70*70/2
scoremaps = [get_scoremap(img, d, params, n_rois) for d in dims]
sum_scoremaps = sum(scoremaps)

roimap = get_scoremap(sum_scoremaps, args.dim, ['score'], 1)
corner = [axis[0] for axis in roimap[...,0].nonzero()]
coords = [(x, x+d) for x, d in zip(corner, args.dim)]

if args.verbose:
    for i, p in enumerate(params):
        z, y, x = coords
        a = img[z[0]:z[1], y[0]:y[1], x[0]:x[1], i]
        print p, a.min(), a.max(), np.median(a)
        print util.fivenum(a.flatten())
        a = img[..., i]
        print p, a.min(), a.max(), np.median(a)
        print util.fivenum(a.flatten())

print 'Optimal ROI: {}'.format(coords)

# Write mask.
if args.output:
    mask = np.zeros((roimap.shape[0:-1]), dtype=int)
    z, y, x = coords
    mask[z[0]:z[1], y[0]:y[1], x[0]:x[1]] = 1
    with open(args.output, 'wb') as f:
        f.write(mask_to_text(mask[0]))



def roi_position(mask):
    # XXX: Quick and dirty ad hoc hack.
    for y, row in enumerate(mask):
        for x, n in enumerate(row):
            if n:
                return (y, x)

if args.inmask:
    inmask = util.read_mask_file(args.inmask)
    inmask_pos = list(roi_position(inmask))
    inmask_pos[0] -= af.subwindow()[2]
    inmask_pos[1] -= af.subwindow()[4]
    print inmask_pos



def draw_roi(img, y, x, color=(1,0,0)):
    img[y:y+4,x,    :] = color
    img[y:y+4,x+4,  :] = color
    img[y,    x:x+4,:] = color
    img[y+4,  x:x+5,:] = color

if args.graphic:
    import matplotlib
    import matplotlib.pyplot as plt
    import pylab as pl
    plt.rcParams['image.interpolation'] = 'nearest'
    n_cols, n_rows = 3, 1
    fig = plt.figure(figsize=(n_cols*6, n_rows*6))

    ax1 = fig.add_subplot(1, n_cols, 1)
    ax1.set_title('ADC map with manually placed ROI')
    iview = img[0,...,0]
    im = plt.imshow(iview, cmap='gray')

    ax2 = fig.add_subplot(1, n_cols, 2)
    ax2.set_title('Calculated score map')
    pmap = sum_scoremaps
    iview = img[0,...,0]
    pview = pmap[0,...,0]
    imgray = plt.imshow(iview, alpha=1, cmap='gray')
    pview /= pview.max()
    imjet = plt.imshow(pview, alpha=0.8, cmap='jet')

    ax3 = fig.add_subplot(1, n_cols, 3)
    ax3.set_title('Final automatic ROI placement')
    iview = img[0,...,0]
    manual = np.zeros(iview.shape + (4,))
    auto = np.zeros(iview.shape + (4,))
    if args.output:
        draw_roi(manual, *inmask_pos, color=(1,0,0,0.7))
    draw_roi(auto, coords[1][0], coords[2][0], color=(0,1,0,0.7))
    im = plt.imshow(iview, cmap='gray')
    im = plt.imshow(manual)
    im = plt.imshow(auto)

    fig.colorbar(imgray, ax=ax1, shrink=0.65)
    fig.colorbar(imjet, ax=ax2, shrink=0.65)
    fig.colorbar(imgray, ax=ax3, shrink=0.65)

    plt.tight_layout()
    plt.savefig(args.graphic, bbox_inches='tight')
