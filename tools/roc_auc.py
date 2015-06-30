#!/usr/bin/env python2

"""Calculate ROC AUC for parametric maps vs. Gleason scores. Optionally compare
AUCs and draw the ROC curves into a file."""

import argparse
import numpy as np

import dwi.patient
import dwi.util

def parse_args():
    """Parse command-line arguments."""
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--verbose', '-v', action='count',
            help='be more verbose')
    p.add_argument('--patients', default='patients.txt',
            help='patients file')
    p.add_argument('--pmapdir', nargs='+', required=True,
            help='input pmap directory')
    p.add_argument('--threshold', default='3+3',
            help='classification threshold (maximum negative)')
    p.add_argument('--nboot', type=int, default=2000,
            help='number of bootstraps')
    p.add_argument('--voxel', default='all',
            help='index of voxel to use, or all, sole, mean, median')
    p.add_argument('--multilesion', action='store_true',
            help='use all lesions, not just first for each')
    p.add_argument('--autoflip', action='store_true',
            help='flip data when AUC < 0.5')
    p.add_argument('--compare', action='store_true',
            help='do AUC comparison')
    p.add_argument('--figure',
            help='output figure file')
    args = p.parse_args()
    return args

def plot(X, Y, params, filename, autoflip=False):
    """Plot ROCs."""
    import pylab as pl
    X = np.asarray(X)
    Y = np.asarray(Y)
    n_rows, n_cols = len(params), 1
    pl.figure(figsize=(n_cols*6, n_rows*6))
    for x, y, param, row in zip(X, Y, params, range(n_rows)):
        fpr, tpr, auc = dwi.util.calculate_roc_auc(y, x, autoflip=autoflip)
        if args.verbose > 1:
            print '%s:  AUC: %f' % (param, auc)
        else:
            print '%f' % auc
        pl.subplot2grid((n_rows, n_cols), (row, 0))
        pl.plot(fpr, tpr, label='ROC curve (area = %0.2f)' % auc)
        pl.plot([0, 1], [0, 1], 'k--')
        pl.xlim([0.0, 1.0])
        pl.ylim([0.0, 1.0])
        pl.xlabel('False Positive rate')
        pl.ylabel('True Positive rate')
        pl.title('%s' % param)
        pl.legend(loc='lower right')
    if filename:
        print 'Writing %s...' % filename
        pl.savefig(filename, bbox_inches='tight')


args = parse_args()

# Collect all parameters.
X, Y = [], []
Params = []
scores = None
for i, pmapdir in enumerate(args.pmapdir):
    data = dwi.patient.read_pmaps(args.patients, pmapdir, [args.threshold],
            voxel=args.voxel, multiroi=args.multilesion)
    if scores is None:
        scores, groups, group_sizes = dwi.patient.grouping(data)
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
    d = dict(n=len(X[0]),
            ns=len(scores), s=sorted(scores),
            ng=len(groups), g=' '.join(map(str, groups)),
            gs=', '.join(map(str, group_sizes)))
    print 'Samples: {n}'.format(**d)
    print 'Scores: {ns}: {s}'.format(**d)
    print 'Groups: {ng}: {g}'.format(**d)
    print 'Group sizes: {gs}'.format(**d)

# Print AUCs and bootstrapped AUCs.
if args.verbose > 1:
    print '# param  AUC  AUC_BS_mean  lower  upper'
Auc_bs = []
params_maxlen = max(len(p) for p in Params)
for x, y, param in zip(X, Y, Params):
    fpr, tpr, auc = dwi.util.calculate_roc_auc(y, x, autoflip=False)
    if args.autoflip and auc < 0.5:
        x = -x
        fpr, tpr, auc = dwi.util.calculate_roc_auc(y, x)
    # Note: x may now be negated (ROC flipped).
    auc_bs = dwi.util.bootstrap_aucs(y, x, args.nboot)
    avg = np.mean(auc_bs)
    ci1, ci2 = dwi.util.ci(auc_bs)
    d = dict(param=param, auc=auc, avg=avg, ci1=ci1, ci2=ci2)
    if args.verbose:
        s = '{param:%i}  {auc:.3f}  {avg:.3f}  {ci1:.3f}  {ci2:.3f}' % params_maxlen
    else:
        s = '{auc:f}'
    print s.format(**d)
    Auc_bs.append(auc_bs)

# Print bootstrapped AUC comparisons.
if args.compare:
    if args.verbose > 1:
        print '# param1  param2  diff  Z  p'
    done = []
    for i, param_i in enumerate(Params):
        for j, param_j in enumerate(Params):
            if i == j or (i, j) in done or (j, i) in done:
                continue
            done.append((i,j))
            d, z, p = dwi.util.compare_aucs(Auc_bs[i], Auc_bs[j])
            print '%s  %s  %+0.4f  %+0.4f  %0.4f' % (param_i, param_j, d, z, p)

# Plot the ROCs.
if args.figure:
    plot(X, Y, Params, args.figure, autoflip=args.autoflip)
