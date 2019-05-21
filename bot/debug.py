# -*- coding: UTF-8 -*-

# Logging Levels
# --------------
# CRITICAL    50
# ERROR       40
# WARNING     30 default
# INFO        20
# DEBUG       10
# NOTSET       0

import enum
import types
import logging
import datetime
import functools
import threading

import telegram
import telegram.ext

OBJECTS = (telegram.bot.Bot, telegram.update.Update, telegram.message.Message,
           telegram.chat.Chat, telegram.user.User,
           telegram.ext.jobqueue.Job, telegram.ext.jobqueue.JobQueue,
           threading.Thread, types.GeneratorType)

CO1 = '\033[40m\033[33m'
CO2 = '\033[40m\033[31m'
CLR = '\033[0m'


def __format(obj, kvsep=': ', quotes=True):
    # pylint: disable=too-many-return-statements

    if isinstance(obj, (list, tuple)):
        return '[{}]'.format(', '.join(__format(o) for o in obj))

    if isinstance(obj, dict):
        quotes = False if '=' in kvsep else quotes
        return '{{{}}}'.format(', '.join(''.join((__format(k, quotes=quotes),
                                                  kvsep,
                                                  __format(v)))
                                         for k, v in obj.items()))

    if isinstance(obj, (datetime.datetime, datetime.timedelta)):
        return '«{}»'.format(str(obj).split('.')[0])

    if isinstance(obj, OBJECTS):
        return '«{}»'.format(obj.__class__.__name__)

    if isinstance(obj, enum.Enum):
        return str(obj)

    if isinstance(obj, str) and not quotes:
        return obj

    return repr(obj)


def __format_args(args, kwargs):
    lst = []
    if args:
        lst.append(__format(args)[1:-1])
    if kwargs:
        lst.append(__format(kwargs, kvsep='=')[1:-1])
    return ', '.join(lst)


def flogger(func):
    logger = logging.getLogger(func.__module__)
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        logger.debug('%sEntering: %s: %s%s', CO1, func.__name__, __format_args(args, kwargs), CLR)
        result = func(*args, **kwargs)
        logger.debug('%sExiting: %s: %s%s', CO2, func.__name__, __format(result), CLR)
        return result
    return decorator
