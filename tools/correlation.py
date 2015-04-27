#!/usr/bin/env python2

"""Calculate correlation for parametric maps vs. Gleason scores."""

import argparse
import math
import numpy as np
import scipy.stats

import dwi.patient
import dwi.util

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
            help='be more verbose')
    p.add_argument('--patients', default='patients.txt',
            help='patients file')
    p.add_argument('--samplelist', default='samples_all.txt',
            help='sample list file')
    p.add_argument('--pmapdir', nargs='+', required=True,
            help='input pmap directory')
    p.add_argument('--thresholds', nargs='*', default=[],
            help='classification thresholds (group maximums)')
    p.add_argument('--voxel', default='all',
            help='index of voxel to use, or all, mean, median')
    args = p.parse_args()
    return args

def correlation(x, y):
    """Calculate correlation with p-value and confidence interval."""
    assert len(x) == len(y)
    if dwi.util.all_equal(x):
        r = p = lower = upper = np.nan
    else:
        #r, p = scipy.stats.pearsonr(x, y)
        #r, p = scipy.stats.kendalltau(x, y)
        r, p = scipy.stats.spearmanr(x, y)
        n = len(x)
        stderr = 1.0 / math.sqrt(n-3)
        delta = 1.96 * stderr
        lower = math.tanh(math.atanh(r) - delta)
        upper = math.tanh(math.atanh(r) + delta)
    return dict(r=r, p=p, lower=lower, upper=upper)

def grouping(data):
    """Return different scores, grouped scores, and their sample sizes."""
    scores = [d['score'] for d in data]
    labels = [d['label'] for d in data]
    n_labels = max(labels) + 1
    groups = [[] for _ in range(n_labels)]
    for s, l in zip(scores, labels):
        groups[l].append(s)
    group_scores = [sorted(set(g)) for g in groups]
    group_sizes = [len(g) for g in groups]
    return sorted(set(scores)), group_scores, group_sizes


# Collect all parameters.
args = parse_args()
X, Y = [], []
Params = []
labels = None
for i, pmapdir in enumerate(args.pmapdir):
    data = dwi.patient.read_pmaps(args.samplelist, args.patients, pmapdir,
            args.thresholds, voxel=args.voxel)
    if labels is None:
        labels, groups, group_sizes = grouping(data)
    for j, param in enumerate(data[0]['params']):
        x, y = [], []
        for d in data:
            for v in d['pmap']:
                x.append(v[j])
                y.append(d['label'])
        X.append(np.asarray(x))
        Y.append(np.asarray(y))
        Params.append('%i:%s' % (i, param))

# Print info.
if args.verbose > 1:
    d = dict(ns=len(X[0]),
            nl=len(labels), l=sorted(labels),
            ng=len(groups), g=' '.join(map(str, groups)),
            gs=', '.join(map(str, group_sizes)))
    print 'Samples: {ns}'.format(**d)
    print 'Labels: {nl}: {l}'.format(**d)
    print 'Groups: {ng}: {g}'.format(**d)
    print 'Group sizes: {gs}'.format(**d)

# Print correlations.
if args.verbose > 1:
    print '# param  r  p  lower  upper'
params_maxlen = max(len(p) for p in Params)
for x, y, param in zip(X, Y, Params):
    d = dict(param=param)
    d.update(correlation(x, y))
    if args.verbose:
        s = '{param:%i}  {r:+.3f}  {p:.3f}  {lower:+.3f}  {upper:+.3f}' % params_maxlen
    else:
        s = '{r:+.3f}'
    print s.format(**d)
