"""Routines for handling patient lists."""

from __future__ import division, print_function
from functools import total_ordering
import os.path

import numpy as np

import dwi.asciifile
import dwi.files
import dwi.util

@total_ordering
class GleasonScore(object):
    """Gleason score is a two or three-value measure of prostate cancer
    severity.
    """
    def __init__(self, score):
        """Intialize with a sequence or a string like '3+4+5' (third digit is
        optional)."""
        if isinstance(score, str) or isinstance(score, unicode):
            s = score.split('+')
        else:
            s = score
        s = tuple(int(x) for x in s)
        if len(s) == 2:
            s += (0,) # Internal representation always has three digits.
        if not len(s) == 3:
            raise Exception('Invalid gleason score: %s', score)
        self.score = s

    def __repr__(self):
        s = self.score
        if not s[-1]:
            s = s[0:-1] # Drop trailing zero.
        return '+'.join(str(x) for x in s)

    def __hash__(self):
        return hash(self.score)

    def __iter__(self):
        return iter(self.score)

    def __eq__(self, other):
        return self.score == other.score

    def __lt__(self, other):
        return self.score < other.score

class Lesion(object):
    """Lesion is a lump of cancer tissue."""
    def __init__(self, index, score, location):
        self.index = index # No. in patient.
        self.score = score # Gleason score.
        self.location = location # PZ or CZ.

    def __repr__(self):
        return repr((self.index, self.score, self.location))

@total_ordering
class Patient(object):
    """Patient case."""
    def __init__(self, num, name, scans, lesions):
        self.num = num
        self.name = name
        self.scans = scans
        self.lesions = lesions
        self.score = lesions[0].score # For backwards compatibility.

    def __repr__(self):
        return repr(self.tuple())

    def __hash__(self):
        return hash(self.tuple())

    def __eq__(self, other):
        return self.tuple() == other.tuple()

    def __lt__(self, other):
        return self.tuple() < other.tuple()

    def tuple(self):
        return self.num, self.name, self.scans, self.lesions

def scan_in_patients(patients, num, scan):
    """Is this scan listed in the patients sequence?"""
    for p in patients:
        if p.num == num and scan in p.scans:
            return True
    return False

def get_patient(patients, num):
    """Search a patient from sequence by patient number."""
    for p in patients:
        if p.num == num:
            return p
    raise Exception('Patient not found: {}'.format(num))

def get_gleason_scores(patients):
    """Get all separate Gleason scores, sorted."""
    #return sorted({p.score for p in patients})
    scores = set()
    for p in patients:
        scores.update(l.score for l in p.lesions)
    return sorted(scores)

def score_ord(scores, score):
    """Get Gleason score's ordinal number."""
    return sorted(scores).index(score)

def load_files(patients, filenames, pairs=False):
    """Load pmap files."""
    pmapfiles = []
    if len(filenames) == 1:
        # Workaround for platforms without shell-level globbing.
        import glob
        l = glob.glob(filenames[0])
        if len(l) > 0:
            filenames = l
    for f in filenames:
        num, scan = dwi.util.parse_num_scan(os.path.basename(f))
        if patients is None or scan_in_patients(patients, num, scan):
            pmapfiles.append(f)
    afs = [dwi.asciifile.AsciiFile(x) for x in pmapfiles]
    if pairs:
        dwi.util.scan_pairs(afs)
    ids = [dwi.util.parse_num_scan(af.basename) for af in afs]
    pmaps = [af.a for af in afs]
    pmaps = np.array(pmaps)
    params = afs[0].params()
    assert pmaps.shape[-1] == len(params), 'Parameter name mismatch.'
    #print('Filenames: %i, loaded: %i, lines: %i, columns: %i'
    #        % (len(filenames), pmaps.shape[0], pmaps.shape[1], pmaps.shape[2]))
    return pmaps, ids, params

def load_labels(patients, nums, labeltype='score'):
    """Load labels according to patient numbers."""
    gs = get_gleason_scores(patients)
    scores = [get_patient(patients, n).score for n in nums]
    if labeltype == 'score':
        # Use Gleason score.
        labels = scores
    elif labeltype == 'ord':
        # Use ordinal.
        labels = [score_ord(gs, s) for s in scores]
    elif labeltype == 'bin':
        # Is aggressive? (ROI1.)
        labels = [s > GleasonScore('3+4') for s in scores]
    elif labeltype == 'cancer':
        # Is cancer? (ROI1 vs 2, all true for ROI1.)
        labels = [1] * len(scores)
    else:
        raise Exception('Invalid parameter: %s' % labeltype)
    return labels

def cases_scans(patients, cases=(), scans=()):
    """Generate all case, scan combinations, with optional whitelists."""
    for p in patients:
        if not cases or p.num in cases:
            for s in p.scans:
                if not scans or s in scans:
                    yield p.num, s

def lesions(patients):
    """Generate all case, scan, lesion combinations."""
    for p in patients:
        for s in p.scans:
            for l in p.lesions:
                yield p, s, l

# Low group: 3 only; intermediate: 4 secondary or tertiary w/o 5; high: rest.
THRESHOLDS_STANDARD = ('3+3', '3+4')

def read_pmaps(patients_file, pmapdir, thresholds=('3+3',), voxel='all',
               multiroi=False):
    """Read pmaps labeled by their Gleason score.

    Label thresholds are maximum scores of each label group. Labels are ordinal
    of score if no thresholds provided."""
    # TODO Support for selecting measurements over scan pairs
    thresholds = tuple(GleasonScore(x) for x in thresholds)
    patients = dwi.files.read_patients_file(patients_file)
    gs = get_gleason_scores(patients)
    data = []
    for patient, scan, lesion in lesions(patients):
        if not multiroi and lesion.index != 0:
            continue
        case = patient.num
        score = lesion.score
        if thresholds:
            label = sum(score > t for t in thresholds)
        else:
            label = score_ord(gs, score)
        roi = lesion.index if multiroi else None
        pmap, params, pathname = read_pmap(pmapdir, case, scan, roi=roi,
                                           voxel=voxel)
        d = dict(case=case, scan=scan, roi=lesion.index, score=score,
                 label=label, pmap=pmap, params=params, pathname=pathname)
        data.append(d)
        if pmap.shape != data[0]['pmap'].shape:
            raise Exception('Irregular shape: %s' % pathname)
        if params != data[0]['params']:
            raise Exception('Irregular params: %s' % pathname)
    return data

def grouping(data):
    """Return different scores, grouped scores, and their sample sizes.

    See read_pmaps()."""
    scores = [d['score'] for d in data]
    labels = [d['label'] for d in data]
    n_labels = max(labels) + 1
    groups = [[] for _ in range(n_labels)]
    for s, l in zip(scores, labels):
        groups[l].append(s)
    different_scores = sorted(set(scores))
    group_scores = [sorted(set(g)) for g in groups]
    group_sizes = [len(g) for g in groups]
    return different_scores, group_scores, group_sizes

def read_pmap(dirname, case, scan, roi=None, voxel='all'):
    """Read single pmap."""
    d = dict(d=dirname, c=case, s=scan, r=roi)
    if roi is None:
        s = '{d}/{c}_*{s}*.txt'
    else:
        d['r'] += 1
        s = '{d}/{c}_*{s}_{r}*.txt'
    path = dwi.util.sglob(s.format(**d))
    af = dwi.asciifile.AsciiFile(path)
    pmap = af.a
    params = af.params()
    if pmap.shape[-1] != len(params):
        # TODO Move to Asciifile initializer?
        raise Exception('Number of parameters mismatch: %s' % af.filename)
    # Select voxel to use.
    if voxel == 'all':
        pass # Use all voxels.
    elif voxel == 'sole':
        # Use sole voxel (raise exception if more found).
        if len(pmap) != 1:
            raise Exception('Too many voxels: {}'.format(len(pmap)))
    elif voxel == 'mean':
        pmap = np.mean(pmap, axis=0, keepdims=True) # Use mean voxel.
    elif voxel == 'median':
        pmap = dwi.util.median(pmap, axis=0, keepdims=True) # Use median voxel.
    else:
        pmap = pmap[[int(voxel)]] # Use single voxel only.
    return pmap, params, af.filename
