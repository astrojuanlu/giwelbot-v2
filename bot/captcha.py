# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán

import re
import random
import operator

from debug import flogger

OPERATORS = '+-*/'
MAX_NUMBER = 9
MIN_SEPARATION = 2
MAX_NUMBER_ANSWERS = (MAX_NUMBER * 2 + 1) / MIN_SEPARATION

OPERATOR_FUNC = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
}

SPACE = ('\u0020\u00a0\u2002\u2003\u2004\u2005\u2006'
         '\u2007\u2008\u2009\u200a\u202f\u205f\u200b\ufeff')

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
    assert num_answers <= MAX_NUMBER_ANSWERS, 'num_answers exceeds the safe limit'
    # Because of the inclusion of the operands (`num_a` and `num_b`), the result
    # (`answer`) and the union of the operands (`num_a num_b`) the maximum
    # number can be up to 4 more than the MAX_NUMBER_ANSWERS but cannot be
    # guaranteed right now

    operator_sym = random.choice(OPERATORS)
    operator_func = OPERATOR_FUNC[operator_sym]
    while True:
        num_a = random.randint(0, MAX_NUMBER)
        num_b = random.randint(0, MAX_NUMBER)
        try:
            answer = operator_func(num_a, num_b)
            abs_answer = abs(answer)
            int_answer = int(answer)
            if abs_answer < MAX_NUMBER and int_answer == answer:
                break
        except ZeroDivisionError:
            pass

    # Obfuscation
    captcha = get_captcha_text(num_a, operator_sym, num_b)

    # Correct and fake answers
    correct_answer = str(int_answer)
    answers = []
    if num_answers > 4:
        if num_a != answer:
            answers.append(f'{num_a}')
            if num_a != 0:
                answers.append(f'{num_a}{num_b}')
        if num_b not in (answer, num_a):
            answers.append(f'{num_b}')

    limit = num_answers - 1
    while len(answers) < limit:
        num = random.randint(-MAX_NUMBER, MAX_NUMBER)
        if abs(abs_answer - abs(num)) > MIN_SEPARATION:
            num = str(num)
            if num not in answers and num != correct_answer:
                answers.append(num)

    random.shuffle(answers)
    # Never put the correct_answer in the beginning
    answers.insert(random.randint(1, limit), correct_answer)
    return captcha, correct_answer, answers
