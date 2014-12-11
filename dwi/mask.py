"""ROI masks."""

import re
import numpy as np

import dwi.util

class Mask(object):
    """Mask for one slice in 3D image."""
    def __init__(self, slice, array):
        if slice < 1:
            raise Exception('Invalid slice')
        self.slice = slice # Slice number, one-based indexing
        self.array = array.astype(bool) # 2D mask of one slice.

    def __repr__(self):
        return repr((self.slice, self.array.shape))

    def __str__(self):
        return repr(self)

    def get_subwindow(self, coordinates, onebased=True):
        """Get a view of a specific subwindow."""
        if onebased:
            coordinates = [i-1 for i in coordinates] # One-based indexing.
        z0, z1, y0, y1, x0, x1 = coordinates
        slice = self.slice - z0
        array = self.array[y0:y1,x0:x1]
        return Mask(slice, array)

    def get_masked(self, array):
        """Get masked region as a flat array."""
        if array.ndim == self.array.ndim:
            return array[self.array]
        else:
            return array[self.slice-1, self.array]

def load_ascii(filename):
    """Read a ROI mask file."""
    slice = 1
    arrays = []
    with open(filename, 'rU') as f:
        p = re.compile(r'(\w+)\s*:\s*(.*)')
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = p.match(line)
            if m:
                if m.group(1) == 'slice':
                    slice = int(m.group(2))
            elif line[0] == '0' or line[0] == '1':
                a = np.array(list(line), dtype=int)
                arrays.append(a)
    if arrays:
        return Mask(slice, np.array(arrays))
    else:
        raise Exception('No mask found in %s' % filename)

class Mask3D(object):
    """Image mask stored as a 3D array."""
    def __init__(self, a):
        if a.ndim != 3:
            raise 'Invalid mask dimensionality: %s' % a.shape
        self.array = a.astype(bool)

    def __repr__(self):
        return repr(self.array.shape)

    def __str__(self):
        return repr(self)

    def n_selected(self):
        """Return number of selected voxels."""
        return np.count_nonzero(mask)

    def get_masked(self, a):
        """Return masked voxels."""
        return a[self.array]

    def where(self):
        """Return indices of masked voxels."""
        return np.argwhere(self.array)

def read_dicom_mask(path):
    import dwi.dicomfile
    d = dwi.dicomfile.read_dir(path)
    image = d['image']
    image = image.squeeze(axis=3) # Remove single subvalue dimension.
    mask = Mask3D(image)
    return mask
