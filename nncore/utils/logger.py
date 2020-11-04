# Copyright (c) Ye Liu. All rights reserved.

import logging
import os.path as osp
import sys

from termcolor import colored

import nncore

_COLOR_MAP = {
    0: 'white',
    10: 'cyan',
    20: 'green',
    30: 'yellow',
    40: 'red',
    50: 'magenta'
}

_CACHED_LOGGERS = []


class _Formatter(logging.Formatter):

    def formatMessage(self, record):
        log = super(_Formatter, self).formatMessage(record)
        anchor = -len(record.message)
        prefix = colored(log[:anchor], color=_COLOR_MAP[record.levelno])
        return prefix + log[anchor:]


def get_logger(logger_or_name=None,
               fmt='[%(asctime)s %(levelname)s]: %(message)s',
               datefmt='%Y-%m-%d %H:%M:%S',
               log_level=logging.INFO,
               log_file=None):
    """
    Initialize and get a logger by name.

    If the logger has not been initialized, this method will initialize the
    logger by adding one or two handlers, otherwise the initialized logger will
    be directly returned. During initialization, a StreamHandler will always be
    added. If `log_file` is specified and the process rank is 0, a FileHandler
    will also be added.

    Args:
        logger_or_name (:obj:`logging.Logger` or str, optional): the logger or
            name of the logger
        fmt (str, optional): log format. The format must end with `%(message)s`
            to make sure that the colors could be rendered properly.
        datefmt (str, optional): date format
        log_level (str or int, optional): log level of the logger. Note that
            only the main process (rank 0) is affected, and other processes
            will set the level to `ERROR` thus be silent at most of the time.
        log_file (str, optional): filename of the log file. If not None, a
            `FileHandler` will be added to the logger.

    Returns:
        logger (:obj:`logging.Logger`): the expected logger
    """
    if isinstance(logger_or_name, logging.Logger):
        return logger_or_name

    logger = logging.getLogger(logger_or_name)

    if logger_or_name in _CACHED_LOGGERS:
        return logger

    _CACHED_LOGGERS.append(logger_or_name)

    logger.setLevel(log_level)
    logger.propagate = False

    if not fmt.endswith('%(message)s'):
        raise ValueError("fmt must end with '%(message)s'")

    sh = logging.StreamHandler(stream=sys.stdout)
    formatter = _Formatter(fmt=fmt, datefmt=datefmt)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    try:
        from nncore.engine import is_main_process
        if not is_main_process():
            logger.setLevel(logging.ERROR)
            return logger
    except ImportError:
        pass

    if log_file is not None:
        nncore.mkdir(osp.dirname(log_file))
        fh = logging.FileHandler(log_file, mode='w')
        formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


def log_or_print(msg, logger, log_level=logging.INFO, **kwargs):
    """
    Log a message with a potential logger. If `logger` is a valid
    `logging.Logger` or a name of the logger, then it would be used. Otherwise
    this method will use the normal `print` function instead.

    Args:
        msg (str): the message to be logged
        logger (any): the potential logger or name of the logger to be used
        log_level (int, optional): log level of the logger
    """
    level = logging._checkLevel(log_level)
    if isinstance(logger, logging.Logger):
        logger.log(level, msg)
    elif isinstance(logger, str):
        logger = get_logger(logger, **kwargs)
        logger.log(level, msg)
    else:
        if level > 20:
            level_name = logging._levelToName[level]
            msg = '{} {}'.format(
                colored(level_name + ':', color=_COLOR_MAP[level]), msg)
        print(msg)
