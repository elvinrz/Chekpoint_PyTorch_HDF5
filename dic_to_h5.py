from collections import OrderedDict
import json
import logging
import numpy
import os.path
import sys

try:
    import h5py
except ImportError as e:
    h5py_missing = True
    h5py_import_error = e
else:
    h5py_missing = False

from .configdict import ConfigDict
from .utils import is_group, is_file

from silx.io import open as h5open

__authors__ = ["P. Knobel"]
__license__ = "MIT"
__date__ = "10/02/2017"

logger = logging.getLogger(__name__)

string_types = (basestring,) if sys.version_info[0] == 2 else (str,)    # noqa


def _prepare_hdf5_dataset(array_like):
    """Cast a python object into a numpy array in a HDF5 friendly format.

    :param array_like: Input dataset in a type that can be digested by
        ``numpy.array()`` (`str`, `list`, `numpy.ndarray`�)
    :return: ``numpy.ndarray`` ready to be written as an HDF5 dataset
    """
    # simple strings
    if isinstance(array_like, string_types):
        array_like = numpy.string_(array_like)

    # Ensure our data is a numpy.ndarray
    if not isinstance(array_like, (numpy.ndarray, numpy.string_)):
        array = numpy.array(array_like)
    else:
        array = array_like

    # handle list of strings or numpy array of strings
    if not isinstance(array, numpy.string_):
        data_kind = array.dtype.kind
        # unicode: convert to byte strings
        # (http://docs.h5py.org/en/latest/strings.html)
        if data_kind.lower() in ["s", "u"]:
            array = numpy.asarray(array, dtype=numpy.string_)

    return array


def dicttoh5(treedict, h5file, h5path='/',
             mode="w", overwrite_data=False,
             create_dataset_args=None):
    """Write a nested dictionary to a HDF5 file, using keys as member names.

    If a dictionary value is a sub-dictionary, a group is created. If it is
    any other data type, it is cast into a numpy array and written as a
    :mod:`h5py` dataset. Dictionary keys must be strings and cannot contain
    the ``/`` character.

    .. note::

        This function requires `h5py <http://www.h5py.org/>`_ to be installed.

    :param treedict: Nested dictionary/tree structure with strings as keys
         and array-like objects as leafs. The ``"/"`` character is not allowed
         in keys.
    :param h5file: HDF5 file name or handle. If a file name is provided, the
        function opens the file in the specified mode and closes it again
        before completing.
    :param h5path: Target path in HDF5 file in which scan groups are created.
        Default is root (``"/"``)
    :param mode: Can be ``"r+"`` (read/write, file must exist),
        ``"w"`` (write, existing file is lost), ``"w-"`` (write, fail if
        exists) or ``"a"`` (read/write if exists, create otherwise).
        This parameter is ignored if ``h5file`` is a file handle.
    :param overwrite_data: If ``True``, existing groups and datasets can be
        overwritten, if ``False`` they are skipped. This parameter is only
        relevant if ``h5file_mode`` is ``"r+"`` or ``"a"``.
    :param create_dataset_args: Dictionary of args you want to pass to
        ``h5f.create_dataset``. This allows you to specify filters and
        compression parameters. Don't specify ``name`` and ``data``.

    Example::

        from silx.io.dictdump import dicttoh5

        city_area = {
            "Europe": {
                "France": {
                    "Is�re": {
                        "Grenoble": "18.44 km2"
                    },
                    "Nord": {
                        "Tourcoing": "15.19 km2"
                    },
                },
            },
        }

        create_ds_args = {'compression': "gzip",
                          'shuffle': True,
                          'fletcher32': True}

        dicttoh5(city_area, "cities.h5", h5path="/area",
                 create_dataset_args=create_ds_args)
    """
    if h5py_missing:
        raise h5py_import_error

    if not isinstance(h5file, h5py.File):
        h5f = h5py.File(h5file, mode)
    else:
        h5f = h5file

    if not h5path.endswith("/"):
        h5path += "/"

    for key in treedict:

        if isinstance(treedict[key], dict) and len(treedict[key]):
            # non-empty group: recurse
            dicttoh5(treedict[key], h5f, h5path + key,
                     overwrite_data=overwrite_data,
                     create_dataset_args=create_dataset_args)

        elif treedict[key] is None or (isinstance(treedict[key], dict) and
                                       not len(treedict[key])):
            # Create empty group
            h5f.create_group(h5path + key)

        else:
            ds = _prepare_hdf5_dataset(treedict[key])
            # can't apply filters on scalars (datasets with shape == () )
            if ds.shape == () or create_dataset_args is None:
                h5f.create_dataset(h5path + key,
                                   data=ds)
            else:
                h5f.create_dataset(h5path + key,
                                   data=ds,
                                   **create_dataset_args)

    if isinstance(h5file, string_types):
        h5f.close()


def _name_contains_string_in_list(name, strlist):
    if strlist is None:
        return False
    for filter_str in strlist:
        if filter_str in name:
            return True
    return False