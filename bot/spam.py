# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán

import re

CHECKOUT = (
    'caption',
    'forward_signature',
    'forward_from_chat.title',
    'forward_from_chat.username',
    'author_signature',
    'forward_sender_name',
    'text',
)

LETTER_MAP = {
    'a': '\u1972\u1d00',
    'b': '\u0412',
    'c': '\u1d04\u0421',
    'd': '\u0274',
    'e': '\u1971\u1d07\u0415',
    'f': '\u0493',
    'g': '\u0262',
    'h': '',
    'i': '\u03b9\u026a',
    'j': '',
    'k': '\u1d0b',
    'l': '\u1963\u029f',
    'm': '\u043c',
    'n': '\u1952\u0274',
    'o': '\u1d0f',
    'p': '',
    'q': '',
    'r': '\u0280',
    's': '',
    't': '\u0442\u1d1b',
    'u': '\u1d1c',
    'v': '',
    'w': '\u1d21\u03c9',
    'x': '\u0425',
    'y': '',
    'z': '',
}

def flex(char):
    if char in LETTER_MAP:
        return f'[{char}{LETTER_MAP[char]}]'
    return char

SKETCH = '(tg(vip)?member|telegram marketing)'

PATTERN = ''.join((f'{flex(c)}\\s*' if c.isalpha() else c) for c in SKETCH)
SPAMMER_RE = re.compile(PATTERN.replace(r'\s* ', r'\s+'), re.IGNORECASE)

def is_spam(message):
    for checkout in CHECKOUT:
        try:
            attrs = iter(checkout.split('.'))
            obj = message
            while True:
                try:
                    obj = getattr(obj, next(attrs))
                except StopIteration:
                    break
            if SPAMMER_RE.match(str(obj or '')):
                return True
        except AttributeError:
            pass
    return False
