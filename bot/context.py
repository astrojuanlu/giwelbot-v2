# -*- coding: UTF-8 -*-

import functools
import threading

from telegram import Update
from telegram.ext import Job

from debug import flogger


class Context:

    '''Contains the data of a request.'''

    def __init__(self, mem, args, kwargs):
        self.mem = mem
        self.bot = args[0]
        self.__dict__.update(kwargs)

        if isinstance(args[1], Update):
            self.update = args[1]
            self.chat = self.update.effective_chat
            self.user = self.update.effective_user
            self.message = self.update.effective_message

        elif isinstance(args[1], Job):
            self.job = args[1]

            context = self.job.context or []
            if not isinstance(context, (list, tuple)):
                context = [context]
            num = len(context)
            if num > 0:
                self.chat = context[0]
            if num > 1:
                self.user = context[1]

    def __repr__(self):
        return f'«{self.__class__.__name__}»'

    @flogger
    def __contains__(self, var):
        return var in self.__dict__

    @flogger
    def __setitem__(self, var, value):
        self.__dict__[var] = value

    @flogger
    def __delitem__(self, var):
        del self.__dict__[var]

    @flogger
    def __getitem__(self, var):
        if var in self.__dict__:
            return self.__dict__[var]
        return getattr(self, var)

    @flogger
    def __getattr__(self, var):
        if var == 'cid':
            return self.chat.id

        if var == 'uid':
            return self.user.id

        if var == 'from_bot':
            return self.user.id == self.bot.id

        if var == 'is_group':
            return self.chat.type in (self.chat.GROUP, self.chat.SUPERGROUP)

        if var == 'is_private':
            return self.chat.type == self.chat.PRIVATE

        return None  # Caution: does not throw KeyError or AttributeError


class Contextualizer:
    '''
    The Contextualizer object contains the data structure stored in memory
    and a lock for multithreading to access the data.
    Data is stored between requests.
    '''

    __slots__ = ('__lock', '__data', '__keys')

    def __init__(self):
        self.__lock = threading.Lock()
        self.__data = {}
        self.__keys = []

    def __repr__(self):
        return f'«{self.__class__.__name__}»'


    @flogger
    def __contains__(self, keys):
        '''
        Allows to verify if the keys sequence is present.
        '''
        data, key = self.__get_last_data_key(keys, 'get')
        return key in data


    @flogger
    def __getitem__(self, keys):
        '''
        Access an element, if it doesn't exist it returns None
        or the default value passed as slice in last key.
        '''
        data, key = self.__get_last_data_key(keys, 'get')
        if isinstance(key, slice):
            default = key.stop
            key = key.start
        else:
            default = None
        return data.get(key, default)


    @flogger
    def __setitem__(self, keys, value):
        '''
        Set a value in the data.
        '''
        data, key = self.__get_last_data_key(keys, 'setdefault')
        data[key] = value


    @flogger
    def __delitem__(self, keys):
        '''
        Delete a value from the data.
        '''
        data, key = self.__get_last_data_key(keys, 'get')
        del data[key]


    #@flogger
    def __get_last_data_key(self, keys, method):
        '''
        Search for the keys in the data and return
        the last dictionary and the last key.
        '''
        if not isinstance(keys, (list, tuple)):
            keys = (keys,)

        if isinstance(keys[0], slice):
            keys = self.__keys[keys[0]] + list(keys[1:])

        data = self.__data
        for key in keys[:-1]:
            data = getattr(data, method)(key, {})

        return data, keys[-1]


    @flogger
    def get_data(self):
        '''
        Returns the data.
        '''
        return self.__data


    @flogger
    def get_keys(self):
        '''
        Returns the list of keys.
        '''
        return self.__keys


    @flogger
    def add_keys(self, *keys):
        '''
        Add the keys to the list of keys.
        '''
        for key in keys:
            self.__keys.append(key)


    @flogger
    def del_keys(self):
        '''
        Deletes the list of keys.
        '''
        self.__keys.clear()


    @flogger
    def set_keys(self, *keys):
        '''
        Sets the keys as the list of keys.
        '''
        self.__keys.clear()
        self.__keys.extend(keys)


    @flogger
    def mod_key(self, index, value):
        '''
        Modify a specific key.
        '''
        self.__keys[index] = value


    @flogger
    def contains_keys(self, *keys):
        '''
        Checks if a sequence of keys is present.
        '''
        if not keys:
            if self.__keys:
                keys = self.__keys
            else:
                raise IndexError('Must specify the keys')

        data, key = self.__get_last_data_key(keys, 'get')
        return key in data


    @flogger
    def delete_if_empty(self, *keys):
        '''
        Delete keys if empty.
        '''
        if not keys:
            if self.__keys:
                keys = self.__keys
            else:
                raise IndexError('Must specify the keys')

        keys = list(keys)
        while keys:
            data, key = self.__get_last_data_key(keys, 'get')
            if key in data and data[key] == {}:
                del data[key]
                keys.pop()
            else:
                break


    def __call__(self, func):
        '''
        Decorator, safe in threads, to give access to data stored in memory.
        '''
        @functools.wraps(func)
        def decorator(*args, **kwargs):
            ctx = Context(self, args, kwargs)

            keys = []
            if ctx.chat:
                keys.append(ctx.chat.id)
                if ctx.user:
                    keys.append(ctx.user.id)

            with self.__lock:
                self.set_keys(*keys)
                result = func(ctx)

            return result
        return decorator


    @flogger
    def chat_ids(self):
        '''
        Iterate over all stored chat ids.
        '''
        for chat_id in self.__data:
            if isinstance(chat_id, int):  # allow to store other keys
                yield chat_id


    @flogger
    def user_ids(self, chat_id=None):
        '''
        Iterate over all stored user ids of a particular chat id.
        '''
        if not chat_id:
            if self.__keys:
                chat_id = self.__keys[0]
            else:
                raise IndexError('Must specify the chat id')

        for user_id in self.__data.get(chat_id, ()):
            if isinstance(user_id, int):  # allow to store other keys
                yield user_id
