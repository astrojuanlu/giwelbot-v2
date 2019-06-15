# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán

# Logging Levels
# --------------
# CRITICAL    50
# ERROR       40
# WARNING     30 default
# INFO        20
# DEBUG       10
# NOTSET       0

import re
import enum
import types
import logging
import datetime
import functools
import threading

import telegram
import telegram.ext

import sqlalchemy
import database

OBJECTS = (telegram.bot.Bot, telegram.update.Update, telegram.message.Message,
           telegram.chat.Chat, telegram.user.User,
           telegram.ext.jobqueue.Job, telegram.ext.jobqueue.JobQueue,
           types.GeneratorType)

DB_OBJECTS = (sqlalchemy.ext.declarative.api.DeclarativeMeta,
              database.Admission, database.Captcha, database.Restriction,
              database.User, database.Chat)

MAIN_FUNCTIONS_RE = re.compile('^.*_(handler|thread)$')

COLOR_A1 = '\033[40m\033[36m'
COLOR_A2 = '\033[44m\033[1;36m'
COLOR_B1 = '\033[40m\033[37m'
COLOR_B2 = '\033[40m\033[1;37m'
COLOR_RS = '\033[0m'


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
        return f'«{str(obj).split(".")[0]}»'

    if isinstance(obj, OBJECTS):
        return f'«{obj.__class__.__name__}»'

    if isinstance(obj, DB_OBJECTS):
        return f'«{str(obj)}»'

    if isinstance(obj, threading.Thread):
        name = obj.getName()
        if 'thread' not in name.lower():
            name = f'Thread:{name}'
        return f'«{name}»'

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


def get_first_lineno(obj):
    # For cases where there are multiple decorators
    offset = 0  # if the decorators use only one line, give the exact position
    while hasattr(obj, "__wrapped__"):
        obj = obj.__wrapped__
        offset += 1
    return obj.__code__.co_firstlineno + offset


def logger_debug(log, obj, msg, *args):
    # The filename, lineno and function name are modified because
    # otherwise the information in this file (debug.py) would be displayed
    level = logging.DEBUG
    if log.isEnabledFor(level):
        exc_info = None
        extra = None
        filename = obj.__code__.co_filename
        lineno = get_first_lineno(obj) + 1  # +1 for flogger decorator
        func_name = obj.__code__.co_name
        sinfo = None
        record = log.makeRecord(log.name, level, filename, lineno, msg, args,
                                exc_info, func_name, extra, sinfo)
        log.handle(record)


def flogger(func):
    logger = logging.getLogger(func.__module__)

    if MAIN_FUNCTIONS_RE.match(func.__name__):
        color_a = COLOR_A2
        color_b = COLOR_B2
    else:
        color_a = COLOR_A1
        color_b = COLOR_B1

    @functools.wraps(func)
    def decorator(*args, **kwargs):
        logger_debug(logger, func, '%s→ %s: %s%s', color_a,
                     func.__name__, __format_args(args, kwargs), COLOR_RS)
        result = func(*args, **kwargs)
        logger_debug(logger, func, '%s← %s: %s%s', color_b,
                     func.__name__, __format(result), COLOR_RS)
        return result
    return decorator
