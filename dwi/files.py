"""Operations regarding miscellaneous files."""

from __future__ import absolute_import, division, print_function
from contextlib import contextmanager
import logging
import os
import re
import shutil
import tempfile
import zipfile

import numpy as np

try:
    from pathlib import Path, PurePath
except ImportError:
    from pathlib2 import Path, PurePath

import dwi.asciifile
import dwi.dicomfile
import dwi.hdf5
from dwi.patient import Patient, Lesion

log = logging.getLogger(__name__)
COMMENT_PREFIX = '#'


@contextmanager
def temp_dir():
    """A temporary directory context that deletes it afterwards."""
    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir)


@contextmanager
def read_archive(archive, max_size=None):
    """Extract a ZIP archive into a temporary directory, use as a context."""
    with zipfile.ZipFile(archive, 'r') as a:
        infos = a.infolist()
        total_size = sum(x.file_size for x in infos)
        if max_size is not None and total_size > max_size:
            raise ValueError('Archive content is too big', archive)
        with temp_dir() as tmpdir:
            # Extract one by one because the docs warn against extractall().
            log.debug('Extracting %s to %s', archive, tmpdir)
            for info in infos:
                a.extract(info, tmpdir)
            yield tmpdir


def toline(iterable):
    """Convert an iterable into a line."""
    return ' '.join(str(x) for x in iterable) + '\n'


def valid_lines(path):
    """Read and yield lines that are neither empty nor comments."""
    with Path(path).open(mode='rU') as f:
        for line in f:
            line = line.split(COMMENT_PREFIX, 1)[0].strip()
            if line:
                yield line


def ensure_dir(path):
    """Ensure existence of the file's parent directory."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def mapped(shape, dtype, filler=None):
    """Create an array as a memory-mapped temporary file on disk."""
    # import tempfile
    # fileno, path = tempfile.mkstemp(suffix='.texture')
    # a = np.memmap(path, dtype=dtype, mode='w+', shape=shape)
    a = np.memmap(os.tmpfile(), dtype=dtype, mode='w+', shape=shape)
    if filler is not None:
        a.fill(filler)
    return a


def parse_patient(line, include_lines=False):
    """Parse a line in patient list file.
    Format: num name scan1,scan2,... score [location]
    """
    regexp = r"""
        (?P<num>\d+) \s+
        (?P<name>\w+) \s+
        (?P<scans>[\w,]+) \s+
        (?P<score>\d\+\d(\+\d)?) \s* (?P<location>\w+)? \s*
        ((?P<score2>\d\+\d(\+\d)?) \s+ (?P<location2>\w+))? \s*
        ((?P<score3>\d\+\d(\+\d)?) \s+ (?P<location3>\w+))?
        """
    p = re.compile(regexp, flags=re.VERBOSE)
    m = p.match(line)
    if m is None:
        raise Exception('Invalid line in patients file: %s', line)
    num = m.group('num')
    name = m.group('name')
    scans = sorted(m.group('scans').lower().split(','))
    les = [Lesion(0, m.group('score'), 'xx')]
    if m.group('location'):
        # New-style, multi-lesion file.
        les = []
        les.append(Lesion(0, m.group('score'), m.group('location')))
        if m.group('score2'):
            les.append(Lesion(1, m.group('score2'), m.group('location2')))
        if m.group('score3'):
            les.append(Lesion(2, m.group('score3'), m.group('location3')))
    patient = Patient(num, name, scans, les)
    if include_lines:
        patient.line = line
    return patient


def read_patients_file(path, include_lines=False):
    """Read a list of patients."""
    return sorted(parse_patient(x, include_lines=include_lines) for x in
                  valid_lines(path))


def read_sample_list(filename):
    """Read a list of samples from file."""
    entries = []
    p = re.compile(r'(\d+)\s+(\w+)\s+([\w,]+)')
    for line in valid_lines(filename):
        m = p.match(line)
        if m:
            case, name, scans = m.groups()
            case = int(case)
            name = name.lower()
            scans = tuple(sorted(scans.lower().split(',')))
            d = dict(case=case, name=name, scans=scans)
            entries.append(d)
    return entries


def read_subregion_file(filename):
    """Read a subregion definition from file.

    It's formatted as one voxel index per line, zero-based, in order of
    y_first, y_last, x_first, x_last, z_first, z_last. The "last" ones need +1
    to get Python-like start:stop indices. They are returned as (z_start,
    z_stop, y_start, y_stop, x_start, x_stop).
    """
    entries = []
    for line in valid_lines(filename):
        entries.append(int(float(line)))
    if len(entries) != 6:
        raise Exception('Invalid subregion file: %s' % filename)
    entries = entries[4:6] + entries[0:4]  # Move z indices to front.
    # Add one to "last" indices get Python-like start:stop indices.
    entries[1] += 1
    entries[3] += 1
    entries[5] += 1
    return tuple(entries)


def write_comment(f, text):
    """Write zero or more lines to file with comment prefix."""
    for line in text.splitlines():
        f.write('{p} {s}\n'.format(p=COMMENT_PREFIX, s=line))


def write_subregion_file(filename, win, comment=''):
    """Write a subregion definition to file.

    It's formatted as one voxel index per line, zero-based, in order of
    y_first, y_last, x_first, x_last, z_first, z_last.
    """
    if len(win) != 6:
        raise Exception('Invalid subregion: %s' % win)
    entries = [win[2], win[3]-1, win[4], win[5]-1, win[0], win[1]-1]
    with open(filename, 'w') as f:
        write_comment(f, comment)
        for entry in entries:
            f.write('%i\n' % entry)


def guess_format(path):
    """Guess file format identifier from it's suffix."""
    return Path(path).suffix[1:]


def write_pmap(filename, pmap, attrs, fmt=None):
    """Write parametric map file either as HDF5 or ASCII."""
    pmap = np.asanyarray(pmap)
    if pmap.ndim < 2:
        raise Exception('Not enough dimensions: {}'.format(pmap.shape))
    if 'parameters' not in attrs:
        attrs['parameters'] = [str(i) for i in range(pmap.shape[-1])]
    if 'shape' not in attrs:
        attrs['shape'] = pmap.shape
    if 'dtype' not in attrs:
        attrs['dtype'] = str(pmap.dtype)
    if pmap.shape[-1] != len(attrs['parameters']):
        raise Exception('Number of values and parameters mismatch')
    assert all(dwi.util.isstring(x) for x in
               attrs['parameters']), attrs['parameters']
    if fmt is None:
        fmt = guess_format(filename)
    if fmt == 'h5':
        dwi.hdf5.write_hdf5(filename, pmap, attrs)
    elif fmt == 'txt':
        pmap = pmap.reshape((-1, pmap.shape[-1]))  # Can't keep shape.
        dwi.asciifile.write_ascii_file(filename, pmap, None, attrs=attrs)
    else:
        raise Exception('Unknown format: {}'.format(fmt))


def asindices(iterable, lst):
    """Replace items in iterable with their corresponding indices in list, or
    convert them to integers. E.g. asindices(['o', '22'], 'foobar') => 1, 22.
    """
    for item in iterable:
        try:
            yield lst.index(item)  # Yield corresponding index.
        except ValueError:
            yield int(item)  # Not found, convert to integer.


def pick_params(pmap, attrs, params):
    """Select a subset of parameters by their indices or names."""
    params = list(asindices(params, attrs['parameters']))
    pmap = pmap[..., params]
    if 'bset' in attrs and len(attrs['bset']) == len(attrs['parameters']):
        attrs['bset'] = [attrs['bset'][x] for x in params]
    if 'echotimes' in attrs and (len(attrs['echotimes']) ==
                                 len(attrs['parameters'])):
        attrs['echotimes'] = [attrs['echotimes'][x] for x in params]
    attrs['parameters'] = [attrs['parameters'][x] for x in params]
    return pmap, attrs


def read_pmap(path, ondisk=False, fmt=None, params=None, dtype=None):
    """Read a parametric map.

    With parameter ondisk it will not be read into memory. Parameter params
    tells which parameter indices should be included.
    """
    if fmt is None:
        fmt = guess_format(path)
    if fmt == 'h5':
        pmap, attrs = dwi.hdf5.read_hdf5(path, ondisk=ondisk)
    elif fmt == 'txt':
        attrs, pmap = dwi.asciifile.read_ascii_file(path)
        if 'parameters' in attrs:
            attrs['parameters'] = attrs['parameters'].split()
    elif fmt == 'zip':
        with read_archive(path) as tempdir:
            return read_pmap(tempdir, ondisk=ondisk, fmt=None, params=params,
                             dtype=dtype)
    else:
        # No extension, assume it's a DICOM directory.
        d = dwi.dicomfile.read_dir(path)
        pmap = d.pop('image')
        attrs = dict(d)
    if 'parameters' not in attrs:
        attrs['parameters'] = range(pmap.shape[-1])
    attrs['parameters'] = [str(x) for x in attrs['parameters']]
    if params is not None:
        pmap, attrs = pick_params(pmap, attrs, params)
    if dtype is not None:
        pmap = pmap.astype(dtype)
    log.debug('Read %s, %s, %s', path, pmap.shape, pmap.dtype)
    return pmap, attrs


def read_mask(path, expected_voxel_spacing=None, n_dec=3, container=None,
              allowed_outside=0.2):
    """Read pmap as a mask.

    Optionally expect voxel spacing to match up to a certain number of
    decimals. The optional parameter allowed_outside indicates how much of the
    smaller mask (lesion) volume may be outside of a larger container mask
    (prostate) without an error being raised.
    """
    mask, attrs = read_pmap(path)
    mask = mask[..., 0].astype(np.bool)
    if expected_voxel_spacing is not None:
        vs = [round(x, n_dec) for x in attrs['voxel_spacing']]
        evs = [round(x, n_dec) for x in expected_voxel_spacing]
        if vs != evs:
            s = '{}: Expected voxel spacing {}, got {}'
            raise ValueError(s.format(path, evs, vs))
    if container is not None:
        portion_outside_container = (np.count_nonzero(mask[~container]) /
                                     np.count_nonzero(mask))
        if portion_outside_container > allowed_outside:
            s = '{}: Portion of selected voxels outside container is {:%}'
            raise ValueError(s.format(path, portion_outside_container))
    return mask
