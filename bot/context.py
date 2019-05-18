# -*- coding: UTF-8 -*-

import functools
import threading

from telegram import Update, ChatAction
from telegram.ext import Job

from debug import flogger


class Context():
    '''
    The Context object contains the data structure stored in memory
    and a lock for multithreading to access the data.
    '''

    __slots__ = ('__lock', '__data', '__keys')

    def __init__(self):
        self.__lock = threading.Lock()
        self.__data = {}
        self.__keys = []

    def __repr__(self):
        return '«Context»'


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


    @flogger
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
        self.del_keys()
        self.add_keys(*keys)


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
        Decorator, safe in threads, to give access to data stored in memory,
        calls the function that decorates with the parameters it needs.
        '''
        @functools.wraps(func)
        def decorator(*args, **kwargs):

            bot = args[0]
            kwargs['bot'] = bot
            kwargs['data'] = self

            chat = None
            user = None

            if isinstance(args[1], Update):
                update = args[1]
                kwargs['update'] = update
                chat = update.effective_chat
                user = update.effective_user
                bot.send_chat_action(chat.id, ChatAction.TYPING)

            elif isinstance(args[1], Job):
                job = args[1]
                kwargs['job'] = job
                if job.context:
                    if not isinstance(job.context, (list, tuple)):
                        job.context = (job.context,)
                else:
                    job.context = []
                conlen = len(job.context)
                if conlen > 0:
                    chat = job.context[0]
                if conlen > 1:
                    user = job.context[1]

            keys = []
            if chat:
                kwargs['chat'] = chat
                keys.append(chat.id)
                if user:
                    kwargs['user'] = user
                    keys.append(user.id)

            # Vision: "from what I have, I give you what you need"
            required_vars = func.__code__.co_varnames
            available_vars = {k: kwargs[k] for k in kwargs if k in required_vars}

            with self.__lock:
                self.set_keys(*keys)
                result = func(**available_vars)
                self.del_keys()

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
