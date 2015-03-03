#!/usr/bin/env python2

"""Test texture properties for ROI search."""

import argparse
import glob
import re
import numpy as np
import skimage

import dwi.dataset
import dwi.util
import dwi.patient
import dwi.dwimage
import dwi.mask
import dwi.texture

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description = __doc__)
    p.add_argument('--verbose', '-v', action='count',
            help='increase verbosity')
    p.add_argument('--dir', '-d', required=True,
            help='image directory')
    p.add_argument('--cases', '-c', nargs='+', type=int, default=[],
            help='case numbers to draw')
    p.add_argument('--total', '-t', action='store_true',
            help='show total AUC')
    p.add_argument('--step', '-s', type=int, default=5,
            help='window step size')
    args = p.parse_args()
    return args

def read_image(dir, case, scan, model):
    d = dict(d=dir, c=case, s=scan, m=model)
    path = dwi.util.sglob('{d}/{c}_*_{s}/{c}_*_{s}_{m}'.format(**d))
    return dwi.dwimage.load_dicom([path])[0]

def read_mask(dir, case, scan):
    d = dict(d=dir, c=case, s=scan)
    path = dwi.util.sglob('{d}/{c}_{s}_*.mask'.format(**d))
    return dwi.mask.load_ascii(path)

def normalize_pmap(pmap):
    in_range = (0, 0.025)
    pmap = skimage.exposure.rescale_intensity(pmap, in_range=in_range)
    pmap = skimage.img_as_ubyte(pmap)
    return pmap

def read_data(imagedir, patientsfile, subwindowsfile, samplesfile):
    patients = dwi.patient.read_patients_file(patientsfile)
    subwindows = dwi.util.read_subwindows(subwindowsfile)
    samples_all = dwi.util.read_sample_list(samplesfile)
    
    data = dict(cases=[], scans=[], scores=[], images=[], cancer_masks=[],
            normal_masks=[])
    for sample in samples_all:
        case, scans = sample['case'], sample['scans']
        scan = scans[0]
        if case not in args.cases:
            continue
        score = dwi.patient.get_patient(patients, case).score
        subwindow = subwindows[(case, scan)]
        dwimage = read_image(imagedir, case, scan, 'ADCm')
        cancer_mask = read_mask('masks_cancer', case, scan)
        normal_mask = read_mask('masks_normal', case, scan)
    
        assert subwindow[0] == cancer_mask.slice == normal_mask.slice
        assert dwimage.shape()[1:] ==\
                cancer_mask.array.shape == normal_mask.array.shape
        assert np.sum(cancer_mask.array) == np.sum(normal_mask.array) == 25
    
        dwimage = dwimage.get_roi(subwindow)
        cancer_mask = cancer_mask.get_subwindow(subwindow)
        normal_mask = normal_mask.get_subwindow(subwindow)
        img = dwimage.image[0,:,:,0]
        img = normalize_pmap(img)

        data['cases'].append(case)
        data['scans'].append(scan)
        data['scores'].append(score)
        data['cancer_masks'].append(cancer_mask)
        data['normal_masks'].append(normal_mask)
        data['images'].append(img)
    return data

def get_mask_rois(data):
    data['cancer_rois'] = []
    data['normal_rois'] = []
    for img, cmask, nmask in zip(data['images'], data['cancer_masks'],
            data['normal_masks']):
        cancer_roi = cmask.selected(img).reshape((5,5))
        normal_roi = nmask.selected(img).reshape((5,5))
        data['cancer_rois'].append(cancer_roi)
        data['normal_rois'].append(normal_roi)

def get_other_rois(data, win_step):
    l = []
    for img in data['images']:
        windows = skimage.util.view_as_windows(img, (5,5), step=win_step)
        windows = windows.reshape(-1,5,5)
        for win in windows:
            if win.min() > 0:
                l.append(win)
    data['other_rois'] = l

def get_texture_aucs(data):
    aucs = []
    for i, propname in enumerate(dwi.texture.PROPNAMES):
        c = data['cancer_coprops'][:,i]
        n = data['normal_coprops'][:,i]
        o = data['other_coprops'][:,i]
        #print np.mean(c), dwi.util.fivenum(c)
        #print np.mean(n), dwi.util.fivenum(n)
        #print np.mean(o), dwi.util.fivenum(o)
        yc = np.ones_like(c, dtype=int)
        yn = np.ones_like(n, dtype=int)
        yo = np.zeros_like(o, dtype=int)
        y = np.concatenate((yc, yn, yo))
        x = np.concatenate((c, n, o))
        _, _, auc = dwi.util.calculate_roc_auc(y, x, autoflip=True)
        aucs.append(auc)
    return aucs

def draw_props(img, title, win_step):
    pmap = dwi.texture.get_texture_pmap(img, win_step)

    import matplotlib
    import matplotlib.pyplot as plt
    import pylab as pl
    plt.rcParams['image.cmap'] = 'gray'
    plt.rcParams['image.aspect'] = 'equal'
    plt.rcParams['image.interpolation'] = 'none'
    n_cols, n_rows = len(dwi.texture.PROPNAMES)+1, 1
    fig = plt.figure(figsize=(n_cols*6, n_rows*6))
    plt.title(title)
    for i, name in enumerate(['original']+dwi.texture.PROPNAMES):
        ax = fig.add_subplot(1, n_cols, i+1)
        ax.set_title(name)
        plt.imshow(pmap[i])
    #plt.tight_layout()
    outfile = title+'.png'
    print 'Writing %s' % outfile
    plt.savefig(outfile, bbox_inches='tight')


args = parse_args()
data = read_data(args.dir, 'patients.txt', 'subwindows.txt', 'samples_all.txt')
get_mask_rois(data)
get_other_rois(data, args.step)
print 'Window step size: %s' % args.step
print len(data['other_rois'])

print
print dwi.util.fivenum(data['cancer_rois'])
print dwi.util.fivenum(data['normal_rois'])
print dwi.util.fivenum(data['other_rois'])

c = np.array(data['cancer_rois']).ravel()
n = np.array(data['normal_rois']).ravel()
print c.shape, n.shape
#o = np.array(data['other_rois']).ravel()
yc = np.ones_like(c, dtype=int)
yn = np.zeros_like(n, dtype=int)
#yo = np.zeros_like(o, dtype=int)
y = np.concatenate((yc, yn))
x = np.concatenate((c, n))
_, _, auc = dwi.util.calculate_roc_auc(y, x, autoflip=True)
print auc

if args.total:
    data['cancer_coprops'] = dwi.texture.get_coprops(data['cancer_rois'])
    data['normal_coprops'] = dwi.texture.get_coprops(data['normal_rois'])
    data['other_coprops'] = dwi.texture.get_coprops(data['other_rois'])
    import scipy
    import scipy.stats
    for i in range(len(dwi.texture.PROPNAMES)):
        print scipy.stats.spearmanr(data['cancer_coprops'][:,i], data['normal_coprops'][:,i])
    aucs = get_texture_aucs(data)
    for propname, auc in zip(dwi.texture.PROPNAMES, aucs):
        print propname, auc

#tuples = zip(data['images'], data['cases'], data['scans'])
#for img, case, scan in tuples:
#    if case in args.cases:
#        title = '%s %s' % (case, scan)
#        draw_props(img, title, args.step)

print '---'

data = dwi.dataset.dataset_read_samplelist('samples_train.txt', range(10), ['1a', '2a'])
dwi.dataset.dataset_read_patientinfo(data, 'patients.txt')
dwi.dataset.dataset_read_subregions(data, 'bounding_box_100_10pad')
dwi.dataset.dataset_read_pmaps(data, 'results_Mono_combinedDICOM', 'ADCm')
for d in data:
    d['image'] = normalize_pmap(d['image'])
dwi.dataset.dataset_read_prostate_masks(data, 'masks_prostate')
dwi.dataset.dataset_read_roi_masks(data, 'masks_rois', shape=(5,5))
for d in data:
    d['cancer_coprops'] = dwi.texture.get_coprops([d['cancer_roi']])
    d['normal_coprops'] = dwi.texture.get_coprops([d['normal_roi']])

for d in data:
    print d['case'], d['scan'], d['score'], d['image'].shape
    #print d['subregion'], dwi.util.subwindow_shape(d['subregion'])
    print d['cancer_coprops']
    print d['normal_coprops']

c = np.array([d['cancer_roi'] for d in data]).ravel()
n = np.array([d['normal_roi'] for d in data]).ravel()
print c.shape, n.shape
print dwi.util.fivenum(c)
print dwi.util.fivenum(n)

yc = np.ones_like(c, dtype=int)
yn = np.zeros_like(n, dtype=int)
x = np.concatenate((c, n))
y = np.concatenate((yc, yn))
_, _, auc = dwi.util.calculate_roc_auc(y, x, autoflip=True)
print auc