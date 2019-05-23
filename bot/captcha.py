# -*- coding: UTF-8 -*-

import re
import random
import operator

from debug import flogger

OPERATORS = '+-*/'
MAX_NUMBER = 9
MIN_SEPARATION = 2

OPERATOR_FUNC = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
}

CONFUSABLES = {
    '0': '\u0030\u004f\u039f\u041e\u0555\u00d8\u0398',
    '1': '\u0031',
    '2': '\u0032',
    '3': '\u0033\u04e0\u01b7\u021c\u0417',
    '4': '\u0034',
    '5': '\u0035\u01bc\u01bd',
    '6': '\u0036',
    '7': '\u0037',
    '8': '\u0038\u0222\u0223\u09ea\u0a6a',
    '9': '\u0039\u09ed\u0a67\u0b68\ua76e',
    '+': '\u002b\u2795\u253c',
    '-': '\u002d\u2796\u2012\u2013\u2014\u2015\u2212\u2500\u2501\u30fc\uff0d',
    '/': '\u002f\u2797\u00f7\u2044\u2215\u2571',
    '*': '\u274c\u00d7\u0078\u0445\u2179\uff58\u0058\u03a7\u0425\u2573\uff38',
}

SPACE = ('\u0020\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008'
         '\u2009\u200a\u202f\u205f\u200b\ufeff')

INVISIBLE = '\u2061\u2062\u2063\u2064'


def get_confusable(item):
    result = []
    for character in str(item):
        result.append(random.choice(CONFUSABLES[character]))
    return ''.join(result)


def get_space():
    spaces = ''
    # \u200b: ZERO WIDTH SPACE
    # \ufeff: ZERO WIDTH NO-BREAK SPACE
    while re.match('^[\u200b\ufeff]*$', spaces):
        spaces += random.choice(SPACE)
    return spaces


def get_invisible():
    return random.choice(INVISIBLE)


def get_captcha_text(*items):
    chars = []
    chars.append(get_invisible())
    for item in items:
        chars.append(get_space())
        chars.append(get_invisible())
        chars.append(get_confusable(item))
    chars.append(get_space())
    chars.append(get_invisible())
    return ''.join(chars)


@flogger
def get_captcha(num_answers):
    operator_sym = random.choice(OPERATORS)
    operator_func = OPERATOR_FUNC[operator_sym]
    while True:
        num_a = random.randint(0, MAX_NUMBER)
        num_b = random.randint(0, MAX_NUMBER)
        try:
            answer = operator_func(num_a, num_b)
            if abs(answer) < MAX_NUMBER and int(answer) == answer:
                break
        except ZeroDivisionError:
            pass

    # Obfuscation
    captcha = get_captcha_text(num_a, operator_sym, num_b)

    # Add fake answers
    correct_answer = str(int(answer))  # for 1.0 → '1'
    if num_answers > 4:
        num_c = f'{num_a}{num_b}'
        answers = list(set([correct_answer, str(num_a), str(num_b), num_c]))
    else:
        answers = [correct_answer]
    while len(answers) < num_answers:
        num = random.randint(-MAX_NUMBER, MAX_NUMBER)
        if abs(abs(answer) - abs(num)) > MIN_SEPARATION:
            num = str(num)
            if num not in answers:
                answers.append(num)
    random.shuffle(answers)
    return captcha, correct_answer, answers
