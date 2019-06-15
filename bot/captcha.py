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

SPACE = ('\u0020\u00a0\u2002\u2003\u2004\u2005\u2006'
         '\u2007\u2008\u2009\u200a\u202f\u205f\ufeff\u200b')

INVISIBLE = '\u2061\u2062\u2063\u2064'


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
        chars.append(str(item))
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
