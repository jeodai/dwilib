"""Image as an np.ndarray subclass."""

# Subclassing: https://docs.scipy.org/doc/numpy/user/basics.subclassing.html
# Masked array: https://docs.scipy.org/doc/numpy/reference/maskedarray.html

from __future__ import absolute_import, division, print_function

import numpy as np

import dwi.files
from dwi.files import Path
import dwi.util


class Image(np.ndarray):
    """An np.ndarray subclass for representing single image with metadata."""

    def __new__(cls, input_array, info=None):
        obj = np.asarray(input_array).view(cls)
        obj.info = dict(info or {})
        return obj

    def __array_finalize__(self, obj):
        """Finalize creation. Note: a shallow copy of metadata is shared."""
        if obj is not None:
            self.info = getattr(obj, 'info', None)

    # def __array_prepare__(self, out, context=None):
    #     """On the way into ufunc."""
    #     print('__array_prepare__', type(out), id(context))
    #     return np.ndarray.__array_prepare__(self, out, context)
    #     # return super(Image, self).__array_prepare__(out, context)

    # def __array_wrap__(self, out, context=None):
    #     """On the way out of ufunc."""
    #     print('__array_wrap__', type(out), id(context))
    #     return np.ndarray.__array_wrap__(self, out, context)
    #     # return super(Image, self).__array_wrap__(out, context)

    @classmethod
    def read(cls, path, **kwargs):
        """Read a pmap."""
        path = Path(path)
        img, attrs = dwi.files.read_pmap(str(path), **kwargs)
        info = dict(path=path, attrs=attrs,
                    params=attrs.pop('parameters', None),
                    spacing=attrs.pop('voxel_spacing', None))
        obj = cls(img, info=info)
        return obj

    @property
    def params(self):
        return self.info['params']

    @params.setter
    def params(self, value):
        self.info['params'] = value

    @property
    def spacing(self):
        return self.info['spacing']

    @spacing.setter
    def spacing(self, value):
        self.info['spacing'] = value

    def check(self):
        """Check consistency."""
        assert len(self.params) == self.shape[-1]
        assert len(self.spacing) == self.ndim - 1

    def mbb(self, pad=0):
        """Return the minimum bounding box with optional padding.

        Parameter pad can be a tuple of each dimension or a single number. It
        can contain infinity for maximum padding. Hint: try self[self.mbb()].
        """
        return dwi.util.bbox(self, pad=pad)

    def centroid(self):
        """Calculate image centroid, i.e. center of mass, as a tuple of floats.

        NaN values are considered massless.
        """
        return dwi.util.centroid(self)

    def apply_mask(self, mask, background=np.nan):
        """Apply mask by setting all the rest to nan."""
        self[~mask] = background

    def each_param(self):
        """Iterate over parameters."""
        assert self.ndim == 4, self.shape
        assert self.shape[-1] == len(self.params), (self.shape, self.params)
        return ((p, self[:, :, :, i]) for i, p in enumerate(self.params))

    def each_slice(self):
        """Iterate over slices."""
        assert self.ndim in (3, 4), self.shape
        return iter(self)
