# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán
# pylint: disable=too-few-public-methods

import os
import hmac
import enum

from sqlalchemy import create_engine, Column, ForeignKey, UniqueConstraint
from sqlalchemy import BigInteger, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.collections import attribute_mapped_collection

from tools import Sentinel, DT_FMT

LINK = '<a href="tg://user?id={}">{}</a>'
BASE = declarative_base()


class CaptchaStatus(enum.Enum):
    WAITING = 0
    SOLVED = 1
    WRONG = 2


class CaptchaLocation(enum.Enum):
    GROUP = 0
    PRIVATE = 1


class DatabaseEngine:

    def __init__(self, var):
        self.var = var
        self.url = None
        self.engine = None
        self.session = sessionmaker()

    def __repr__(self):
        return f'«{self.__class__.__name__}»'

    def get_session(self, drop_all_tables=False, create_all_tables=False):
        url = os.environ[self.var]
        if url != self.url or drop_all_tables or create_all_tables:
            self.close()
            self.url = url
            self.engine = create_engine(self.url)
            if drop_all_tables:
                BASE.metadata.drop_all(self.engine)
            if create_all_tables:
                BASE.metadata.create_all(self.engine)
            self.session.configure(bind=self.engine)
        return self.session()

    def close(self):
        if self.engine:
            self.engine.dispose()


class Admission(BASE):
    __tablename__ = 'admission'

    id = Column(Integer, primary_key=True)

    chat_id = Column(BigInteger, ForeignKey('chat.id'), nullable=False)
    chat = relationship('Chat', back_populates='admissions')

    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='admissions')

    chat_user_unique = UniqueConstraint(chat_id, user_id)

    join_message_id = Column(BigInteger, nullable=False)
    join_message_date = Column(DateTime, nullable=False)
    to_greet = Column(Boolean, default=True, nullable=False)

    # https://docs.sqlalchemy.org/en/13/orm/tutorial.html
    # https://docs.sqlalchemy.org/en/13/orm/collections.html#passive-deletes
    captchas = relationship('Captcha',
                            back_populates='admission',
                            order_by="Captcha.location_id",
                            single_parent=True,
                            lazy='joined',
                            cascade="all, delete-orphan",
                            passive_deletes=True,
                            collection_class=attribute_mapped_collection('location'))

    def __repr__(self):
        return (f'Admission:{self.id}:CID{self.chat_id}:UID{self.user_id}'
                f':G{self.to_greet}:{self.join_message_date:{DT_FMT}}')

    @property
    def group_captcha(self):
        return self.captchas.get(CaptchaLocation.GROUP, Sentinel())

    #@group_captcha.setter
    #def group_captcha(self, captcha):
    #    if isinstance(captcha, Captcha) and captcha.location is CaptchaLocation.GROUP:
    #        self.captchas[CaptchaLocation.GROUP] = captcha
    #    else:
    #        raise ValueError(str(captcha))

    @property
    def private_captcha(self):
        return self.captchas.get(CaptchaLocation.PRIVATE, Sentinel())

    #@private_captcha.setter
    #def private_captcha(self, captcha):
    #    if isinstance(captcha, Captcha) and captcha.location is CaptchaLocation.PRIVATE:
    #        self.captchas[CaptchaLocation.PRIVATE] = captcha
    #    else:
    #        raise ValueError(str(captcha))


class Captcha(BASE):
    __tablename__ = 'captcha'

    id = Column(Integer, primary_key=True)
    message_id = Column(BigInteger, nullable=False)
    location_id = Column(Integer, nullable=False)
    status_id = Column(Integer, nullable=False)
    token = Column(String(48), nullable=False)
    admission_id = Column(Integer, ForeignKey('admission.id', ondelete="CASCADE"))
    admission = relationship('Admission', back_populates='captchas')

    def __repr__(self):
        return (f'Captcha:{self.id}:{self.location}:{self.status}:'
                f'{self.message_id}:{self.admission_id}')

    @property
    def location(self):
        return CaptchaLocation(self.location_id)

    @location.setter
    def location(self, value):
        self.location_id = CaptchaLocation(value).value

    @property
    def status(self):
        return CaptchaStatus(self.status_id)

    @status.setter
    def status(self, value):
        self.status_id = CaptchaStatus(value).value

    #@property
    #def in_group(self):
    #    return self.location is CaptchaLocation.GROUP

    #@property
    #def in_private(self):
    #    return self.location is CaptchaLocation.PRIVATE

    def is_correct(self, token):
        return hmac.compare_digest(token, self.token)


class Restriction(BASE):
    __tablename__ = 'restriction'

    id = Column(Integer, primary_key=True)

    chat_id = Column(BigInteger, ForeignKey('chat.id'), nullable=False)
    chat = relationship('Chat', back_populates='restrictions')

    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='restrictions')

    chat_user_unique = UniqueConstraint(chat_id, user_id)

    until = Column(DateTime, nullable=False)

    def __repr__(self):
        return (f'Restriction:{self.id}:CID{self.chat_id}:UID{self.user_id}'
                f':{self.until:{DT_FMT}}')


class Expulsion(BASE):
    __tablename__ = 'expulsion'

    id = Column(Integer, primary_key=True)

    chat_id = Column(BigInteger, ForeignKey('chat.id'), nullable=False)
    chat = relationship('Chat', back_populates='expulsions')

    user_id = Column(BigInteger, ForeignKey('user.id'), nullable=False)
    user = relationship('User', back_populates='expulsions')

    reason = Column(String, nullable=False)
    until = Column(DateTime, nullable=False)

    def __repr__(self):
        return (f'Expulsion:{self.id}:CID{self.chat_id}:UID{self.user_id}:'
                f'{self.until:{DT_FMT}}:{self.reason}')


class Chat(BASE):
    __tablename__ = 'chat'

    id = Column(BigInteger, primary_key=True)
    title = Column(String(64))
    prev_greet_users = Column(String(4096))
    prev_greet_message_id = Column(BigInteger)
    admissions = relationship('Admission', back_populates='chat')
    restrictions = relationship('Restriction', back_populates='chat')
    expulsions = relationship('Expulsion', back_populates='chat')

    def __repr__(self):
        return (f'Chat:{self.id}:{self.title}:'
                f'{self.prev_greet_message_id}:{self.prev_greet_users}')


class User(BASE):
    __tablename__ = 'user'

    id = Column(BigInteger, primary_key=True)
    strikes = Column(Integer, default=0, nullable=False)
    admissions = relationship('Admission', back_populates='user')
    restrictions = relationship('Restriction', back_populates='user')
    expulsions = relationship('Expulsion', back_populates='user')

    def __repr__(self):
        return f'User:{self.id}:{self.strikes}'
