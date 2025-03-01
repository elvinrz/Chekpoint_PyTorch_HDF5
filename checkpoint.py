# coding: utf-8
# /*##########################################################################
# Copyright (C) 2016-2017 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ############################################################################*/
"""This module offers a set of functions to dump a python dictionary indexed
by text strings to following file formats: `HDF5, INI, JSON`
"""

from collections import OrderedDict
import json
import logging
import numpy
import os.path
import sys
import torch

try:
    import h5py
except ImportError as e:
    h5py_missing = True
    h5py_import_error = e
else:
    h5py_missing = False

from .configdict import ConfigDict
from .utils import is_group, is_file

from .utils import open as h5open

__authors__ = ["P. Knobel"]
__license__ = "MIT"
__date__ = "10/02/2017"

logger = logging.getLogger(__name__)

string_types = (basestring,) if sys.version_info[0] == 2 else (str,)    # noqa


def _prepare_hdf5_dataset(array_like):
    """Cast a python object into a numpy array in a HDF5 friendly format.

    :param array_like: Input dataset in a type that can be digested by
        ``numpy.array()`` (`str`, `list`, `numpy.ndarray`…)
    :return: ``numpy.ndarray`` ready to be written as an HDF5 dataset
    """
    # simple strings
    if isinstance(array_like, string_types):
        array_like = numpy.string_(array_like)

    # Ensure our data is a numpy.ndarray
    if not isinstance(array_like, int):
        array_like = array_like.cpu().numpy()
         #print(array_like)
    
    if not isinstance(array_like, (numpy.ndarray, numpy.string_)):
        array = numpy.array(array_like)
    else:
        array = array_like

    return array


def save_checkpoint(treedict, h5file, h5path='/',
             mode="w", overwrite_data=False,
             create_dataset_args=None):
    """Write a nested dictionary to a HDF5 file, using keys as member names.

    If a dictionary value is a sub-dictionary, a group is created. If it is
    any other data type, it is cast into a numpy array and written as a
    :mod:`h5py` dataset. Dictionary keys must be strings and cannot contain
    the ``/`` character.

    .. note::

        This function requires `h5py <http://www.h5py.org/>`_ to be installed.
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
            save_checkpoint(treedict[key], h5f, h5path + key, overwrite_data=overwrite_data, create_dataset_args=create_dataset_args)

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


def load_checkpoint(h5file, path="/", exclude_names=None):
    """Read a HDF5 file and return a nested dictionary with the complete file
    structure and all data.

    Example of usage::

        from silx.io.dictdump import h5todict

        # initialize dict with file header and scan header
        header94 = h5todict("oleg.dat",
                            "/94.1/instrument/specfile")
        # add positioners subdict
        header94["positioners"] = h5todict("oleg.dat",
                                           "/94.1/instrument/positioners")
        # add scan data without mca data
        header94["detector data"] = h5todict("oleg.dat",
                                             "/94.1/measurement",
                                             exclude_names="mca_")


    .. note:: This function requires `h5py <http://www.h5py.org/>`_ to be
        installed.

    .. note:: If you write a dictionary to a HDF5 file with
        :func:`dicttoh5` and then read it back with :func:`h5todict`, data
        types are not preserved. All values are cast to numpy arrays before
        being written to file, and they are read back as numpy arrays (or
        scalars). In some cases, you may find that a list of heterogeneous
        data types is converted to a numpy array of strings.

    """
    if h5py_missing:
        raise h5py_import_error

    if not is_file(h5file):
        h5f = h5open(h5file)
    else:
        h5f = h5file

    ddict = OrderedDict()
    #ddict = {}
    for key in h5f[path]:
        if _name_contains_string_in_list(key, exclude_names):
            continue
        if is_group(h5f[path + "/" + key]):
            ddict[key] = load_checkpoint(h5f,
                                  path + "/" + key,
                                  exclude_names=exclude_names)
        else:
            # Convert HDF5 dataset to numpy array
            ddict[key] =  torch.from_numpy(h5f[path + "/" + key][...])

    if not is_file(h5file):
        # close file, if we opened it
        h5f.close()


    
    return ddict


def dicttojson(ddict, jsonfile, indent=None, mode="w"):
    """Serialize ``ddict`` as a JSON formatted stream to ``jsonfile``.

    :param ddict: Dictionary (or any object compatible with ``json.dump``).
    :param jsonfile: JSON file name or file-like object.
        If a file name is provided, the function opens the file in the
        specified mode and closes it again.
    :param indent: If indent is a non-negative integer, then JSON array
        elements and object members will be pretty-printed with that indent
        level. An indent level of ``0`` will only insert newlines.
        ``None`` (the default) selects the most compact representation.
    :param mode: File opening mode (``w``, ``a``, ``w+``…)
    """
    if not hasattr(jsonfile, "write"):
        jsonf = open(jsonfile, mode)
    else:
        jsonf = jsonfile

    json.dump(ddict, jsonf, indent=indent)

    if not hasattr(jsonfile, "write"):
        jsonf.close()


def dicttoini(ddict, inifile, mode="w"):
    """Output dict as configuration file (similar to Microsoft Windows INI).

    :param dict: Dictionary of configuration parameters
    :param inifile: INI file name or file-like object.
        If a file name is provided, the function opens the file in the
        specified mode and closes it again.
    :param mode: File opening mode (``w``, ``a``, ``w+``…)
    """
    if not hasattr(inifile, "write"):
        inif = open(inifile, mode)
    else:
        inif = inifile

    ConfigDict(initdict=ddict).write(inif)

    if not hasattr(inifile, "write"):
        inif.close()


def dump(ddict, ffile, mode="w", fmat=None):
    """Dump dictionary to a file

    :param ddict: Dictionary with string keys
    :param ffile: File name or file-like object with a ``write`` method
    :param str fmat: Output format: ``"json"``, ``"hdf5"`` or ``"ini"``.
        When None (the default), it uses the filename extension as the format.
        Dumping to a HDF5 file requires `h5py <http://www.h5py.org/>`_ to be
        installed.
    :param str mode: File opening mode (``w``, ``a``, ``w+``…)
        Default is *"w"*, write mode, overwrite if exists.
    :raises IOError: if file format is not supported
    """
    if fmat is None:
        # If file-like object get its name, else use ffile as filename
        filename = getattr(ffile, 'name', ffile)
        fmat = os.path.splitext(filename)[1][1:]  # Strip extension leading '.'
    fmat = fmat.lower()

    if fmat == "json":
        dicttojson(ddict, ffile, indent=2, mode=mode)
    elif fmat in ["hdf5", "h5"]:
        if h5py_missing:
            logger.error("Cannot dump to HDF5 format, missing h5py library")
            raise h5py_import_error
        save_checkpoint(ddict, ffile, mode=mode)
    elif fmat in ["ini", "cfg"]:
        dicttoini(ddict, ffile, mode=mode)
    else:
        raise IOError("Unknown format " + fmat)


def load(ffile, fmat=None):
    """Load dictionary from a file

    When loading from a JSON or INI file, an OrderedDict is returned to
    preserve the values' insertion order.

    :param ffile: File name or file-like object with a ``read`` method
    :param fmat: Input format: ``json``, ``hdf5`` or ``ini``.
        When None (the default), it uses the filename extension as the format.
        Loading from a HDF5 file requires `h5py <http://www.h5py.org/>`_ to be
        installed.
    :return: Dictionary (ordered dictionary for JSON and INI)
    :raises IOError: if file format is not supported
    """
    if not hasattr(ffile, "read"):
        f = open(ffile, "r")
        fname = ffile
    else:
        f = ffile
        fname = ffile.name

    if fmat is None:  # Use file extension as format
        fmat = os.path.splitext(fname)[1][1:]  # Strip extension leading '.'
    fmat = fmat.lower()

    if fmat == "json":
        return json.load(f, object_pairs_hook=OrderedDict)
    if fmat in ["hdf5", "h5"]:
        if h5py_missing:
            logger.error("Cannot load from HDF5 format, missing h5py library")
            raise h5py_import_error
        return load_checkpoint(fname)
    elif fmat in ["ini", "cfg"]:
        return ConfigDict(filelist=[fname])
    else:
        raise IOError("Unknown format " + fmat)