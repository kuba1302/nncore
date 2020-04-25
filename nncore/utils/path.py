# Copyright (c) Ye Liu. All rights reserved.

import os
import os.path as osp
from platform import system


def dir_exist(dir_name, raise_error=False):
    """
    Check whether a directory exists.

    Args:
        dir_name (str): (positive or relative) path to the directory
        raise_error (bool, optional): if True, raise a NotADirectoryError when
            the directory not found
    """
    isdir = osp.isdir(dir_name)
    if not isdir and raise_error:
        raise NotADirectoryError("directory '{}' not found".format(dir_name))
    return isdir


def file_exist(filename, raise_error=False):
    """
    Check whether a file exists.

    Args:
        filename (str): (positive or relative) path to the file
        raise_error (bool, optional): if True, raise a FileNotFoundError when
            the file not found
    """
    isfile = osp.isfile(filename)
    if not isfile and raise_error:
        raise FileNotFoundError("file '{}' not found".format(filename))
    return isfile


def mkdir(dir_name, exist_ok=True):
    """
    Create a leaf directory and all intermediate ones.

    Args:
        dir_name (str): (positive or relative) path to the directory
        exist_ok (bool, optional): if false, raise an OSError when the
            directory exists
    """
    assert isinstance(dir_name, str) and dir_name != ''
    dir_name = osp.expanduser(dir_name)
    os.makedirs(dir_name, exist_ok=exist_ok)


def symlink(src, dst, overwrite=True, safe_mode=True):
    """
    Create a symlink from source to destination.

    Args:
        src (str): source of the symlink
        dst (str): destination of the symlink
        overwrite (bool, optional): if true, overwrite it when an old symlink
            exists
        safe_mode (bool, optional): if true, do not raise error when the
            platform does not support symlink
    """
    if system() == 'Windows' and safe_mode:
        return

    if osp.lexists(dst):
        if not overwrite:
            raise FileExistsError("file '{}' exists".format(dst))
        os.remove(dst)
    os.symlink(src, dst)