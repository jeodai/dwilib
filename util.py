import sys
import itertools
import re
import random
import numpy as np
from scipy.stats import scoreatpercentile
import sklearn.metrics

def scale(a, min=0.0, max=1.0):
    """Scale data between given values."""
    # FIXME: min, max parameters don't work
    std = (a - a.min()) / (a.max() - a.min())
    return std / (max - min) + min

def finites(a):
    """Return finite elements as a flat array."""
    return np.array(filter(np.isfinite, a.flat))

def impute(a):
    """Set missing (non-finite) values to mean. Return their number."""
    cnt = 0
    m = finites(a).mean()
    for i, v in enumerate(a):
        if not np.isfinite(v):
            a[i] = m
            cnt += 1
    return cnt

def zeros_to_small(a):
    """Turn zeros into small positives."""
    for i in range(len(a)):
        if a[i] == 0:
            a[i] = 1e-9

def resize(array, min_size):
    """Extend array of arrays to minimum size."""
    while len(array) < min_size:
        array.append([])

def fabricate_subwindow(size, height=None):
    """Fabricate a subwindow specification."""
    if height:
        width = size / height
        if height * width == size:
            return [0, height-1, 0, width-1]
        else:
            return fabricate_subwindow(size, height + 1)
    else:
        return fabricate_subwindow(size, int(np.sqrt(size)))

def combinations(l):
    """Return combinations of list elements."""
    return [x for x in itertools.product(*l)]

def chunks(seq, n):
    """Return sequence as chunks of n elements."""
    return (seq[i:i+n] for i in xrange(0, len(seq), n))

def pairs(seq):
    """Return sequence split in two, each containing every second item."""
    assert len(seq) % 2 == 0, 'Sequence length not even.'
    return (seq[0::2], seq[1::2])

def get_indices(seq, val):
    """Return indices of elements containing given value in a sequence."""
    r = []
    for i, v in enumerate(seq):
        if v == val:
            r.append(i)
    return r



def resample_bootstrap_single(a):
    """Get a bootstrap resampled group for single array."""
    indices = [random.randint(0, len(a)-1) for _ in a]
    return a[indices]

def resample_bootstrap(Y, X):
    """Get a bootstrap resampled group without stratification."""
    indices = [random.randint(0, len(Y)-1) for _ in Y]
    return Y[indices], X[indices]

def resample_bootstrap_stratified(Y, X):
    """Get a bootstrap resampled group with stratification.
    
    Note that as a side-effect the resulting Y array will be sorted, but that
    doesn't matter because X will be randomized accordingly.
    """
    uniques = np.unique(Y)
    indices = []
    for u in uniques:
        l = get_indices(Y, u)
        l_rnd = [l[random.randint(0, len(l)-1)] for _ in l]
        for v in l_rnd:
            indices.append(v)
    return Y[indices], X[indices]

def fivenum(a):
    """Tukey five-number summary (min, q1, median, q3, max)."""
    q1 = scoreatpercentile(a, 25)
    q3 = scoreatpercentile(a, 75)
    return min(a), q1, np.median(a), q3, max(a)

def fivenumd(a):
    """Tukey five-number summary (min, q1, median, q3, max)."""
    min = np.min(a)
    q1 = scoreatpercentile(a, 25)
    median = np.median(a)
    q3 = scoreatpercentile(a, 75)
    max = np.max(a)
    return dict(min=min, q1=q1, median=median, q3=q3, max=max)

def stem_and_leaf(values):
    # XXX: only first and second decimal places
    stems = {}
    for v in sorted(values):
        a = stems.setdefault(int(v*10), [])
        a.append(int((v*10 - int(v*10)) * 10))
    strings = []
    for i in range(11):
        strings.append('%i|%s' % (i, ''.join(map(str, stems.get(i, [])))))
    return strings

def tilde(a):
    """Logical 'not' operator for NumPy objects that behaves like MATLAB
    tilde."""
    typ = a.dtype
    return (~a.astype(bool)).astype(typ)

def roc(truths, scores):
    """Calculate ROC curve."""
    truths = np.array(truths)
    scores = np.array(scores)
    indices_sorted = scores.argsort()
    scores = scores[indices_sorted]
    truths = truths[indices_sorted]
    values = np.unique(scores)
    tp = np.array(values)
    tn = np.array(values)
    fp = np.array(values)
    fn = np.array(values)
    for i, value in enumerate(values):
        c = np.ones_like(scores)
        c[scores >= value] = 0 # Set classifications.
        tp[i] = sum(c * truths)
        tn[i] = sum(tilde(c) * tilde(truths))
        fp[i] = sum(c * tilde(truths))
        fn[i] = sum(tilde(c) * truths)
    fpr = fp / (fp+tn)
    tpr = tp / (tp+fn)
    acc = np.mean((tp+tn) / (tp+fp+fn+tn))
    return fpr, tpr, acc

def roc_auc(fpr, tpr):
    """Calculate ROC AUC."""
    area = 0
    for i in range(len(fpr))[1:]:
        area += abs(fpr[i]-fpr[i-1]) * (tpr[i]+tpr[i-1]) / 2
    return area

def calculate_roc_auc(y, x):
    """Calculate ROC and AUC, negating the estimates if more suitable."""
    fpr, tpr, thresholds = sklearn.metrics.roc_curve(y, x)
    roc_auc = sklearn.metrics.auc(fpr, tpr)
    return fpr, tpr, roc_auc

def negate_for_roc(X, params):
    """Negate certain parameters to produce correct ROC."""
    for i, param in enumerate(params):
        if not (param.isdigit() or\
                param.startswith('SI') or\
                param.startswith('K') or\
                param.startswith('Df')):
            X[i] = -X[i]

def ci(x, p=0.05):
    """Confidence interval of a normally distributed array."""
    x = sorted(x)
    l = len(x)
    i1 = int(round((p/2.) * l + 0.5))
    i2 = int(round((1.-p/2.) * l - 0.5))
    ci1 = x[i1]
    ci2 = x[i2]
    return ci1, ci2



def add_dummy_feature(X):
    """Add an extra dummy feature to an array of samples."""
    r = np.ones((X.shape[0], X.shape[1]+1), dtype=X.dtype)
    r[:,:-1] = X
    return r

def split_roi(pmaps):
    """Split samples to ROI1 and 2."""
    l = pmaps.shape[1]
    if l > 1:
        pmaps1 = pmaps[:,0:l/2,:]
        pmaps2 = pmaps[:,l/2:,:]
    else:
        pmaps1 = pmaps
        pmaps2 = []
    return pmaps1, pmaps2

def select_measurements(pmaps, numsscans, meas):
    """Select measurement baselines to use."""
    if meas == 'all':
        r = pmaps, numsscans
    elif meas == 'mean':
        r = baseline_mean(pmaps, numsscans)
    elif meas == 'a':
        r = pmaps[0::2], numsscans[0::2]
    elif meas == 'b':
        r = pmaps[1::2], numsscans[1::2]
    else:
        raise Exception('Invalid measurement identifier: %s' % meas)
    return r

def baseline_mean(pmaps, numsscans):
    """Take means of each pair of pmaps."""
    baselines = np.array(pairs(pmaps))
    pmaps = np.mean(baselines, axis=0)
    numsscans = pairs(numsscans)[0]
    return pmaps, numsscans

def get_group_id(groups, value):
    """Get group id of a single value."""
    for i, group in enumerate(groups):
        if value in group:
            return i
    return len(groups)

def group_labels(groups, values):
    """Replace labels with group id's.
    
    Parameter groups is a sequence of sequences that indicate labels belonging
    to each group. Default group will be len(groups)."""
    group_ids = []
    for value in values:
        group_ids.append(get_group_id(groups, value))
    return group_ids



def get_args(n=1):
    if len(sys.argv) < 1 + n + 1:
        print 'Need parameters'
        sys.exit(1)
    return sys.argv[1:1+n], sys.argv[1+n:]

def parse_filename(filename):
    """Parse input filename formatted as 'num_name_hB_[12][ab]_*'."""
    m = re.match(r'(\d+)_([\w_]+)_[hH][bB]_(\d\w)_', filename)
    if m:
        num, name, scan = m.groups()
        num = int(num)
        name = name.lower()
        scan = scan.lower()
        return num, name, scan
    return None

def parse_num_scan(filename):
    """Like parse_filename() but return only num, scan."""
    num, name, scan = parse_filename(filename)
    return num, scan

def scan_pairs(afs):
    """Check that the ascii files are correctly paired as scan baselines. Return
    list of (patient number, scan 1, scan 2) tuples."""
    baselines = pairs(afs)
    r = []
    for af1, af2 in zip(*baselines):
        num1, name1, scan1 = parse_filename(af1.basename)
        num2, name2, scan2 = parse_filename(af2.basename)
        if num1 != num2 or scan1[0] != scan2[0]:
            raise Exception('Not a pair: %s, %s' % (af1.basename, af2.basename))
        r.append((num1, scan1, scan2))
    return r
