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
import logging
import functools

import telegram
import telegram.ext

OBJECTS = (telegram.bot.Bot, telegram.update.Update, telegram.message.Message,
           telegram.chat.Chat, telegram.user.User,
           telegram.ext.jobqueue.Job, telegram.ext.jobqueue.JobQueue)


def __format(obj, kvsep=': '):
    if isinstance(obj, (list, tuple)):
        return '[{}]'.format(', '.join(__format(o) for o in obj))

    if isinstance(obj, dict):
        return '{{{}}}'.format(', '.join(''.join((__format(k), kvsep, __format(v)))
                                         for k, v in obj.items()))

    if isinstance(obj, OBJECTS):
        return '«{}»'.format(obj.__class__.__name__)

    if isinstance(obj, enum.Enum):
        return str(obj)

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
        logger.debug('Entering: %s: %s', func.__name__, __format_args(args, kwargs))
        result = func(*args, **kwargs)
        logger.debug('Exiting: %s: %s', func.__name__, __format(result))
        return result
    return decorator
