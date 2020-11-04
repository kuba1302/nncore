# Copyright (c) Ye Liu. All rights reserved.

from collections.abc import Iterable, Sequence
from functools import partial
from itertools import chain


def iter_cast(inputs, dst_type, return_type=None):
    """
    Cast elements of an iterable object into some type.

    Args:
        inputs (Iterable): the input object
        dst_type (type): destination type
        return_type (type, optional): the type of returned object. If
            specified, the output object will be converted to this type,
            otherwise an iterator.

    Returns:
        out_iter (iterator or specified type): the converted object
    """
    if not isinstance(inputs, Iterable):
        raise TypeError('inputs must be an iterable object')
    if not isinstance(dst_type, type):
        raise TypeError("'dst_type' must be a valid type")

    out_iter = map(dst_type, inputs)

    if return_type is not None:
        out_iter = return_type(out_iter)

    return out_iter


def list_cast(inputs, dst_type):
    """
    Cast elements of an iterable object into a list of some type.

    A partial method of :func:`iter_cast`.
    """
    return iter_cast(inputs, dst_type, return_type=list)


def tuple_cast(inputs, dst_type):
    """
    Cast elements of an iterable object into a tuple of some type.

    A partial method of :func:`iter_cast`.
    """
    return iter_cast(inputs, dst_type, return_type=tuple)


def is_seq_of(seq, expected_type, seq_type=None):
    """
    Check whether it is a sequence of some type.

    Args:
        seq (Sequence): the sequence to be checked
        expected_type (type): expected type of sequence items
        seq_type (type, optional): expected sequence type

    Returns:
        flag (bool): whether the sequence is valid
    """
    if seq_type is None:
        exp_seq_type = Sequence
    else:
        assert isinstance(seq_type, type)
        exp_seq_type = seq_type
    if not isinstance(seq, exp_seq_type):
        return False
    for item in seq:
        if not isinstance(item, expected_type):
            return False
    return True


def is_list_of(seq, expected_type):
    """
    Check whether it is a list of some type.

    A partial method of :func:`is_seq_of`.
    """
    return is_seq_of(seq, expected_type, seq_type=list)


def is_tuple_of(seq, expected_type):
    """
    Check whether it is a tuple of some type.

    A partial method of :func:`is_seq_of`.
    """
    return is_seq_of(seq, expected_type, seq_type=tuple)


def slice_list(in_list, lens):
    """
    Slice a list into several sub lists by a list of given length.

    Args:
        in_list (list): the list to be sliced
        lens (int or list): the expected length of each out list

    Returns:
        out_list (list): a list of sliced list
    """
    if isinstance(lens, int):
        assert len(in_list) % lens == 0
        lens = [lens] * int(len(in_list) / lens)
    if not isinstance(lens, list):
        raise TypeError("'indices' must be an integer or a list of integers")
    elif sum(lens) != len(in_list):
        raise ValueError(
            'sum of lens and list length does not match: {} != {}'.format(
                sum(lens), len(in_list)))
    out_list = []
    idx = 0
    for i in range(len(lens)):
        out_list.append(in_list[idx:idx + lens[i]])
        idx += lens[i]
    return out_list


def concat_list(in_list):
    """
    Concatenate a list of list into a single list.

    Args:
        in_list (list): the list of list to be merged

    Returns:
        out_list (list): the concatenated flat list
    """
    return list(chain(*in_list))


def to_dict_of_list(in_list):
    """
    Convert a list of dict to a dict of list.

    Args:
        in_list (list): the list of dict to be converted

    Returns:
        out_dict (dict): the converted dict of list
    """
    for i in range(len(in_list) - 1):
        if in_list[i].keys() != in_list[i + 1].keys():
            raise ValueError('dict keys are not consistent')

    out_dict = dict()
    for key in in_list[0]:
        out_dict[key] = [item[key] for item in in_list]

    return out_dict


def to_list_of_dict(in_dict):
    """
    Convert a dict of list to a list of dict.

    Args:
        in_dict (dict): the dict of list to be converted

    Returns:
        out_list (list): the converted list of dict
    """
    values = in_dict.values()
    for i in range(len(in_dict) - 1):
        if len(values[i]) != len(values[i + 1]):
            raise ValueError('lengths of lists are not consistent')

    out_list = []
    for i in range(len(in_dict)):
        out_list.append({k: v[i] for k, v in in_dict.items()})

    return out_list


def bind_getter(*vars):
    """
    A syntactic sugar for automatically binding getters for classes. This
    method is expected to be used as a decorator.

    Args:
        *vars: strings indicating the member variables to be binded with
            getters. The name of member variables are expected to start with an
            underline (e.g. `_name` or `_epoch`).

    Examples:
        >>> @bind_getter('name', 'depth')
        >>> class Backbone:
        ...     _name = 'ResNet'
        ...     _depth = 50
    equals to:
        >>> class Backbone:
        ...     _name = 'ResNet'
        ...     _depth = 50
        ...     @property
        ...     def name(self):
        ...         return self._name
        ...     @property
        ...     def depth(self):
        ...         return self._depth
    """

    def _wrapper(cls):
        for var in vars:
            method = partial(
                lambda self, key: getattr(self, key, None),
                key='_{}'.format(var))
            setattr(cls, var, property(method))
        return cls

    return _wrapper
