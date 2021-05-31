# Chekpoint_PyTorch_HDF5

This library was used to save and load HDF5 checkpoints in PyTorch.  The library requires `h5py <http://www.h5py.org/>`_ to be used.

Two basic functions can be used with the library: 
1) save_checkpoint (dictionary, file_name,target_path)
    - dictionary:  Nested dictionary that contains the model of the neural network to be saved. Only the neural network model can be saved, other types of objects are not supported.
    - file_name: Checkpoint file name. 
    - target_path: Target path in which the checkpoint is created.  Default is root (`` "./" ``).
2) load_checkpoint(file_name,target_path)
    -file_name: Name of the file in hdf5 format to load. This file should have been previously created with the save_checkpoint function.
    -target_path: Name of HDF5 group to use as dictionary root level. Default is root (`` "./" ``).
