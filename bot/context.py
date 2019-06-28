# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán

import time
import logging
import datetime
import functools
import threading

from telegram import Update, TelegramError
from telegram.ext import Job

from sqlalchemy.sql import and_, or_, exists

from debug import flogger
from tools import Sentinel
from database import (DatabaseEngine, Admission, Captcha,
                      Restriction, Expulsion, Chat, User)

HTML_NO_PREVIEW = {'parse_mode': 'HTML', 'disable_web_page_preview': True}


def get_query(query, chat_id=None, user_id=None):
    if chat_id:
        query = query.filter_by(chat_id=chat_id)

    if user_id:
        query = query.filter_by(user_id=user_id)

    if chat_id and user_id:
        return query.first()
    return query.all()


def no_null(value):
    if value:
        return value
    return Sentinel()


class Context:
    # pylint: disable=too-many-instance-attributes

    '''Contains the data of a request.'''

    def __init__(self, mem, dbs, args, kwargs):
        self.logger = logging.getLogger(__name__)

        self.mem = mem
        self.dbs = dbs
        self.bot = args[0]

        self.tgc = Sentinel()
        self.tgu = Sentinel()
        self.tgm = Sentinel()

        self.chat = Sentinel()
        self.user = Sentinel()

        self.update = Sentinel()
        self.job = Sentinel()

        self.admission = Sentinel()
        self.expulsion = Sentinel()
        self.restriction = Sentinel()

        self.__dict__.update(kwargs)

        if isinstance(args[1], Update):
            self.update = args[1]
            self.tgc = self.update.effective_chat
            self.tgu = self.update.effective_user
            self.tgm = self.update.effective_message

        elif isinstance(args[1], Job):
            self.job = args[1]

            context = self.job.context or []
            if not isinstance(context, (list, tuple)):
                context = [context]
            num = len(context)
            if num > 0:
                self.tgc = context[0]
            if num > 1:
                self.tgu = context[1]

        if self.tgu:
            self.user = no_null(self.get_user(id=self.tgu.id))

        if self.tgc and self.is_group:
            self.chat = no_null(self.get_chat(id=self.tgc.id, title=self.tgc.title))
            if self.tgu:
                params = {'chat_id': self.tgc.id, 'user_id': self.tgu.id}
                self.admission = no_null(self.get_admissions(**params))
                self.restriction = no_null(self.get_restrictions(**params))
                self.expulsion = no_null(self.get_expulsions(**params))

        # Definition alias to methods
        params = HTML_NO_PREVIEW.copy()

        if self.tgc:
            params['chat_id'] = self.cid

        self.send = self._define(self.bot.send_message, **params)

        if self.tgm:
            params['message_id'] = self.mid

        self.edit = self._define(self.bot.edit_message_text, **params)


    def __repr__(self):
        return f'«{self.__class__.__name__}»'


    #@flogger
    def _define(self, func, **params):
        @functools.wraps(func)
        def decorator(**kwargs):
            result = None
            try:
                result = func(**{**params, **kwargs})
            except TelegramError as tge:
                self.logger.warning('%s: %s', func.__name__, tge)
            return result
        return decorator


    @property
    def cid(self):
        return self.tgc.id

    @property
    def uid(self):
        return self.tgu.id

    @property
    def mid(self):
        return self.tgm.message_id

    @property
    def text(self):
        return self.tgm.text or ''

    @property
    def date(self):
        return self.tgm.date


    @property
    def from_bot(self):
        return self.tgu.id == self.bot.id

    @property
    def is_group(self):
        return self.tgc.type in (self.tgc.GROUP, self.tgc.SUPERGROUP)

    @property
    def is_private(self):
        return self.tgc.type == self.tgc.PRIVATE


    #@flogger
    def _get_db_obj(self, model, attributes):
        query = self.dbs.query(model).filter_by(id=attributes['id'])
        obj = query.first()
        if obj:
            for var, val in attributes.items():
                if var != 'id':
                    setattr(obj, var, val)
        else:
            obj = model(**attributes)
            self.dbs.add(obj)
        return obj

    @flogger
    def get_chat(self, **attributes):
        return self._get_db_obj(Chat, attributes)

    @flogger
    def get_user(self, **attributes):
        return self._get_db_obj(User, attributes)


    @flogger
    def get_admissions(self, *, chat_id=None, user_id=None):
        query = self.dbs.query(Admission)
        return get_query(query, chat_id, user_id)

    @flogger
    def get_restrictions(self, *, chat_id=None, user_id=None):
        query = self.dbs.query(Restriction)
        return get_query(query, chat_id, user_id)

    @flogger
    def get_expulsions(self, *, chat_id=None, user_id=None):
        # Expulsions are stored for a period of time
        query = self.dbs.query(Expulsion).order_by(Expulsion.until.desc())
        query = query.group_by(Expulsion.id, Expulsion.chat_id)
        return get_query(query, chat_id, user_id)


class Contextualizer:

    __slots__ = ('logger', 'lock', 'mem', 'dbe')

    def __init__(self, env_database, delta_delete_admissions):
        self.logger = logging.getLogger(__name__)
        self.lock = threading.Lock()
        self.mem = {}
        self.dbe = DatabaseEngine(env_database)
        self.initialize(delta_delete_admissions)


    def __repr__(self):
        return f'«{self.__class__.__name__}»'


    def __call__(self, func):
        @functools.wraps(func)
        def decorator(*args, **kwargs):
            dbs = self.dbe.get_session()
            self.logger.debug('db open')
            result = None
            try:
                start = time.time()
                with self.lock:
                    self.logger.debug('%s wait %.3f seconds', func.__name__,
                                      time.time() - start)
                    ctx = Context(self.mem, dbs, args, kwargs)
                    self.logger.debug('go to %s', func.__name__)
                    result = func(ctx)
            except:
                self.logger.exception('db rollback')
                dbs.rollback()
                raise
            else:
                self.logger.debug('db commit')
                dbs.commit()
            finally:
                self.logger.debug('db close')
                dbs.close()
            return result
        return decorator


    def initialize(self, delta_delete_admissions):
        now = datetime.datetime.now()
        adm_lim = now - delta_delete_admissions
        exp_lim = now - 90 * delta_delete_admissions
        dbs = self.dbe.get_session(create_all_tables=True)

        # sql = (
        #     'DELETE FROM admission WHERE join_message_date < ":adm_lim";',
        #     'DELETE FROM captcha',
        #     '       WHERE NOT EXISTS (SELECT *',
        #     '                         FROM admission',
        #     '                         WHERE admission.id == captcha.admission_id);',
        #     'DELETE FROM restriction WHERE until < ":now";',
        #     'DELETE FROM expulsion WHERE until < ":exp_lim";',
        #     'DELETE FROM user',
        #     '       WHERE user.strikes == 0 AND NOT (',
        #     '             EXISTS (SELECT *',
        #     '                     FROM "admission"',
        #     '                     WHERE admission.user_id == user.id)',
        #     '          OR EXISTS (SELECT *',
        #     '                     FROM "expulsion"',
        #     '                     WHERE expulsion.user_id == user.id)',
        #     '          OR EXISTS (SELECT *',
        #     '                     FROM "restriction"',
        #     '                     WHERE restriction.user_id == user.id));'
        # )
        # times = {'now': now, 'adm_lim': adm_lim, 'exp_lim': exp_lim}
        # dbs.execute('\n'.join(sql), times)

        queries = (
            # Expired Admissions
            dbs.query(Admission).filter(Admission.join_message_date < adm_lim),
            # In case passive-deletes doesn't work for Admission
            dbs.query(Captcha).filter(
                ~exists().where(Admission.id == Captcha.admission_id)
            ),
            # Expired Restriction
            dbs.query(Restriction).filter(Restriction.until < now),
            # Expired Expulsion
            dbs.query(Expulsion).filter(Expulsion.until < exp_lim),
            # Users without strikes and events
            dbs.query(User).filter(
                and_(
                    User.strikes == 0,
                    ~or_(
                        exists().where(Admission.user_id == User.id),
                        exists().where(Expulsion.user_id == User.id),
                        exists().where(Restriction.user_id == User.id),
                    )
                )
            )
        )
        for query in queries:
            query.delete(synchronize_session=False)
            dbs.expire_all()
        dbs.commit()
        dbs.close()
