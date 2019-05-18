# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán

# https://unicode.org/cldr/utility/confusables.jsp
# https://www.compart.com/en/unicode/

import re
import random
import operator

from debug import flogger

OPERATORS = '+-*/'
MAX_NUMBER = 18
MIN_SEPARATION = 4

OPERATOR_FUNC = {
    '+': operator.add,
    '-': operator.sub,
    '*': operator.mul,
    '/': operator.truediv,
}

CONFUSABLES = {
    '0': (
        '\u0030',  # DIGIT ZERO
        '\u004F',  # LATIN CAPITAL LETTER O
        '\u039F',  # GREEK CAPITAL LETTER OMICRON
        '\u041E',  # CYRILLIC CAPITAL LETTER O
        '\u0555',  # ARMENIAN CAPITAL LETTER OH
        '\u0B20',  # ORIYA LETTER TTHA
        '\u0B66',  # ORIYA DIGIT ZERO
        '\u3007',  # IDEOGRAPHIC NUMBER ZERO
        '\uFF2F',  # FULLWIDTH LATIN CAPITAL LETTER O
        '\u24EA',  # CIRCLED DIGIT ZERO
        '\u00D8',  # LATIN CAPITAL LETTER O WITH STROKE
        '\u006F',  # LATIN SMALL LETTER O
        '\u00F8',  # LATIN SMALL LETTER O WITH STROKE
        '\u019F',  # LATIN CAPITAL LETTER O WITH MIDDLE TILDE
        '\u0398',  # GREEK CAPITAL LETTER THETA
        '\u03B8',  # GREEK SMALL LETTER THETA
        '\u03F4',  # GREEK CAPITAL THETA SYMBOL
        '\u0472',  # CYRILLIC CAPITAL LETTER FITA
        '\u04E8',  # CYRILLIC CAPITAL LETTER BARRED O
        '\uA74A',  # LATIN CAPITAL LETTER O WITH LONG STROKE OVERLAY
        '\u03A9',  # GREEK CAPITAL LETTER OMEGA
        '\u2126',  # OHM SIGN
        '\u03BF',  # GREEK SMALL LETTER OMICRON
        '\u03C3',  # GREEK SMALL LETTER SIGMA
        '\u043E',  # CYRILLIC SMALL LETTER O
        '\u0585',  # ARMENIAN SMALL LETTER OH
        '\u0A66',  # GURMUKHI DIGIT ZERO
        '\u0AE6',  # GUJARATI DIGIT ZERO
        '\u0D20',  # MALAYALAM LETTER TTHA
        '\u0ED0',  # LAO DIGIT ZERO
        '\u1D0F',  # LATIN LETTER SMALL CAPITAL O
        '\u0051',  # LATIN CAPITAL LETTER Q
    ),
    '1': (
        '\u0031',  # DIGIT ONE
        '\u0049',  # LATIN CAPITAL LETTER I
        '\u006C',  # LATIN SMALL LETTER L
        '\u01C0',  # LATIN LETTER DENTAL CLICK
        '\u0399',  # GREEK CAPITAL LETTER IOTA
        '\u0406',  # CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
        '\u04C0',  # CYRILLIC LETTER PALOCHKA
        '\u2160',  # ROMAN NUMERAL ONE
        '\u217C',  # SMALL ROMAN NUMERAL FIFTY
        '\u2223',  # DIVIDES
        '\u2460',  # CIRCLED DIGIT ONE
        '\u2780',  # DINGBAT CIRCLED SANS-SERIF DIGIT ONE
        '\u278A',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT ONE
        '\u2474',  # PARENTHESIZED DIGIT ONE
    ),
    '2': (
        '\u0032',  # DIGIT TWO
        '\u01A7',  # LATIN CAPITAL LETTER TONE TWO
        '\uA644',  # CYRILLIC CAPITAL LETTER REVERSED DZE
        '\u2461',  # CIRCLED DIGIT TWO
        '\u2781',  # DINGBAT CIRCLED SANS-SERIF DIGIT TWO
        '\u278B',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT TWO
        '\u1D22',  # LATIN LETTER SMALL CAPITAL Z
        '\u2124',  # DOUBLE-STRUCK CAPITAL Z
        '\u2475',  # PARENTHESIZED DIGIT TWO
    ),
    '3': (
        '\u0033',  # DIGIT THREE
        '\u01B7',  # LATIN CAPITAL LETTER EZH
        '\u021C',  # LATIN CAPITAL LETTER YOGH
        '\u0417',  # CYRILLIC CAPITAL LETTER ZE
        '\u04E0',  # CYRILLIC CAPITAL LETTER ABKHASIAN DZE
        '\u2462',  # CIRCLED DIGIT THREE
        '\u2782',  # DINGBAT CIRCLED SANS-SERIF DIGIT THREE
        '\u278C',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT THREE
        '\u018E',  # LATIN CAPITAL LETTER REVERSED E
        '\u2203',  # THERE EXISTS
        '\u2476',  # PARENTHESIZED DIGIT THREE
    ),
    '4': (
        '\u0034',  # DIGIT FOUR
        '\u2463',  # CIRCLED DIGIT FOUR
        '\u2783',  # DINGBAT CIRCLED SANS-SERIF DIGIT FOUR
        '\u278D',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT FOUR
        '\u2477',  # PARENTHESIZED DIGIT FOUR
    ),
    '5': (
        '\u0035',  # DIGIT FIVE
        '\u01BC',  # LATIN CAPITAL LETTER TONE FIVE
        '\u2464',  # CIRCLED DIGIT FIVE
        '\u2784',  # DINGBAT CIRCLED SANS-SERIF DIGIT FIVE
        '\u278E',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT FIVE
        '\u0053',  # LATIN CAPITAL LETTER S
        '\u0405',  # CYRILLIC CAPITAL LETTER DZE
        '\u054F',  # ARMENIAN CAPITAL LETTER TIWN
        '\u0073',  # LATIN SMALL LETTER S
        '\u01BD',  # LATIN SMALL LETTER TONE FIVE
        '\u0455',  # CYRILLIC SMALL LETTER DZE
        '\u2478',  # PARENTHESIZED DIGIT FIVE
    ),
    '6': (
        '\u0036',  # DIGIT SIX
        '\u0431',  # CYRILLIC SMALL LETTER BE
        '\u2465',  # CIRCLED DIGIT SIX
        '\u2785',  # DINGBAT CIRCLED SANS-SERIF DIGIT SIX
        '\u278F',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT SIX
        '\u0047',  # LATIN CAPITAL LETTER G
        '\u2479',  # PARENTHESIZED DIGIT SIX
    ),
    '7': (
        '\u0037',  # DIGIT SEVEN
        '\u2466',  # CIRCLED DIGIT SEVEN
        '\u2786',  # DINGBAT CIRCLED SANS-SERIF DIGIT SEVEN
        '\u2790',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT SEVEN
        '\u247A',  # PARENTHESIZED DIGIT SEVEN
    ),
    '8': (
        '\u0038',  # DIGIT EIGHT
        '\u0222',  # LATIN CAPITAL LETTER OU
        '\u0223',  # LATIN SMALL LETTER OU
        '\u09EA',  # BENGALI DIGIT FOUR
        '\u0A6A',  # GURMUKHI DIGIT FOUR
        '\u2467',  # CIRCLED DIGIT EIGHT
        '\u2787',  # DINGBAT CIRCLED SANS-SERIF DIGIT EIGHT
        '\u2791',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT EIGHT
        '\u0042',  # LATIN CAPITAL LETTER B
        '\u0392',  # GREEK CAPITAL LETTER BETA
        '\u0412',  # CYRILLIC CAPITAL LETTER VE
        '\u00DF',  # LATIN SMALL LETTER SHARP S
        '\u247B',  # PARENTHESIZED DIGIT EIGHT
    ),
    '9': (
        '\u0039',  # DIGIT NINE
        '\u09ED',  # BENGALI DIGIT SEVEN
        '\u0A67',  # GURMUKHI DIGIT ONE
        '\u0B68',  # ORIYA DIGIT TWO
        '\uA76E',  # LATIN CAPITAL LETTER CON
        '\u2468',  # CIRCLED DIGIT NINE
        '\u2788',  # DINGBAT CIRCLED SANS-SERIF DIGIT NINE
        '\u2792',  # DINGBAT NEGATIVE CIRCLED SANS-SERIF DIGIT NINE
        '\u0071',  # LATIN SMALL LETTER Q
        '\u051B',  # CYRILLIC SMALL LETTER QA
        '\u0563',  # ARMENIAN SMALL LETTER GIM
        '\u0566',  # ARMENIAN SMALL LETTER ZA
        '\u0261',  # LATIN SMALL LETTER SCRIPT G
        '\u0581',  # ARMENIAN SMALL LETTER CO
        '\u247C',  # PARENTHESIZED DIGIT NINE
    ),
    '+': (
        '\u002B',  # PLUS SIGN
        '\u2795',  # HEAVY PLUS SIGN
        '\u253C',  # BOX DRAWINGS LIGHT VERTICAL AND HORIZONTAL
    ),
    '-': (
        '\u2012',  # FIGURE DASH
        '\u2013',  # EN DASH
        '\u2014',  # EM DASH
        '\u2015',  # HORIZONTAL BAR
        '\u2212',  # MINUS SIGN
        '\u2796',  # HEAVY MINUS SIGN
        '\u2500',  # BOX DRAWINGS LIGHT HORIZONTAL
        '\u2501',  # BOX DRAWINGS HEAVY HORIZONTAL
        '\u30FC',  # KATAKANA-HIRAGANA PROLONGED SOUND MARK
        '\uFF0D',  # FULLWIDTH HYPHEN-MINUS
    ),
    '/': (
        '\u002F',  # SOLIDUS
        '\u2044',  # FRACTION SLASH
        '\u2215',  # DIVISION SLASH
        '\u2571',  # BOX DRAWINGS LIGHT DIAGONAL UPPER RIGHT TO LOWER LEFT
        '\u00F7',  # DIVISION SIGN
        '\u2797',  # HEAVY DIVISION SIGN
    ),
    '*': (
        '\u00D7',  # MULTIPLICATION SIGN
        '\u0078',  # LATIN SMALL LETTER X
        '\u0445',  # CYRILLIC SMALL LETTER HA
        '\u2179',  # SMALL ROMAN NUMERAL TEN
        '\uFF58',  # FULLWIDTH LATIN SMALL LETTER X
        '\u0058',  # LATIN CAPITAL LETTER X
        '\u03A7',  # GREEK CAPITAL LETTER CHI
        '\u0425',  # CYRILLIC CAPITAL LETTER HA
        '\u2573',  # BOX DRAWINGS LIGHT DIAGONAL CROSS
        '\uFF38',  # FULLWIDTH LATIN CAPITAL LETTER X
        '\u03C7',  # GREEK SMALL LETTER CHI
        '\u04B2',  # CYRILLIC CAPITAL LETTER HA WITH DESCENDER
        '\u04B3',  # CYRILLIC SMALL LETTER HA WITH DESCENDER
        '\u2715',  # MULTIPLICATION X
        '\u2716',  # HEAVY MULTIPLICATION X
        '\u2717',  # BALLOT X
        '\u2718',  # HEAVY BALLOT X
        '\u274C',  # CROSS MARK
    ),
}

INVISIBLE = (
    '\u2061',  # FUNCTION APPLICATION
    '\u2062',  # INVISIBLE TIMES
    '\u2063',  # INVISIBLE SEPARATOR
    '\u2064',  # INVISIBLE PLUS
)

COMBINING = (
    '\u0302',  # COMBINING CIRCUMFLEX ACCENT
    '\u0303',  # COMBINING TILDE
    '\u0306',  # COMBINING BREVE
    '\u0307',  # COMBINING DOT ABOVE
    '\u0308',  # COMBINING DIAERESIS
    '\u0309',  # COMBINING HOOK ABOVE
    '\u030b',  # COMBINING DOUBLE ACUTE ACCENT
    '\u030c',  # COMBINING CARON
    '\u030d',  # COMBINING VERTICAL LINE ABOVE
    '\u030e',  # COMBINING DOUBLE VERTICAL LINE ABOVE
    '\u0310',  # COMBINING CANDRABINDU
    '\u0311',  # COMBINING INVERTED BREVE
    '\u0312',  # COMBINING TURNED COMMA ABOVE
    '\u0313',  # COMBINING COMMA ABOVE
    '\u0314',  # COMBINING REVERSED COMMA ABOVE
    '\u0315',  # COMBINING COMMA ABOVE RIGHT
    '\u0316',  # COMBINING GRAVE ACCENT BELOW
    '\u0317',  # COMBINING ACUTE ACCENT BELOW
    '\u0318',  # COMBINING LEFT TACK BELOW
    '\u0319',  # COMBINING RIGHT TACK BELOW
    '\u031a',  # COMBINING LEFT ANGLE ABOVE
    '\u031b',  # COMBINING HORN
    '\u031c',  # COMBINING LEFT HALF RING BELOW
    '\u031d',  # COMBINING UP TACK BELOW
    '\u031e',  # COMBINING DOWN TACK BELOW
    '\u031f',  # COMBINING PLUS SIGN BELOW
    '\u0321',  # COMBINING PALATALIZED HOOK BELOW
    '\u0322',  # COMBINING RETROFLEX HOOK BELOW
    '\u0324',  # COMBINING DIAERESIS BELOW
    '\u0325',  # COMBINING RING BELOW
    '\u0326',  # COMBINING COMMA BELOW
    '\u0327',  # COMBINING CEDILLA
    '\u0328',  # COMBINING OGONEK
    '\u0329',  # COMBINING VERTICAL LINE BELOW
    '\u032a',  # COMBINING BRIDGE BELOW
    '\u032b',  # COMBINING INVERTED DOUBLE ARCH BELOW
    '\u032c',  # COMBINING CARON BELOW
    '\u032d',  # COMBINING CIRCUMFLEX ACCENT BELOW
    '\u032e',  # COMBINING BREVE BELOW
    '\u032f',  # COMBINING INVERTED BREVE BELOW
    '\u0339',  # COMBINING RIGHT HALF RING BELOW
    '\u033a',  # COMBINING INVERTED BRIDGE BELOW
    '\u033d',  # COMBINING X ABOVE
    '\u033e',  # COMBINING VERTICAL TILDE
    '\u0340',  # COMBINING GRAVE TONE MARK
    '\u0341',  # COMBINING ACUTE TONE MARK
    '\u0342',  # COMBINING GREEK PERISPOMENI
    '\u0343',  # COMBINING GREEK KORONIS
    '\u0344',  # COMBINING GREEK DIALYTIKA TONOS
    '\u0345',  # COMBINING GREEK YPOGEGRAMMENI
    '\u0346',  # COMBINING BRIDGE ABOVE
    '\u0347',  # COMBINING EQUALS SIGN BELOW
    '\u0348',  # COMBINING DOUBLE VERTICAL LINE BELOW
    '\u0349',  # COMBINING LEFT ANGLE BELOW
    '\u034a',  # COMBINING NOT TILDE ABOVE
    '\u034b',  # COMBINING HOMOTHETIC ABOVE
    '\u034c',  # COMBINING ALMOST EQUAL TO ABOVE
    '\u034d',  # COMBINING LEFT RIGHT ARROW BELOW
    '\u034e',  # COMBINING UPWARDS ARROW BELOW
    '\u034f',  # COMBINING GRAPHEME JOINER
    '\u0351',  # COMBINING LEFT HALF RING ABOVE
    '\u0352',  # COMBINING FERMATA
    '\u0353',  # COMBINING X BELOW
    '\u0354',  # COMBINING LEFT ARROWHEAD BELOW
    '\u0355',  # COMBINING RIGHT ARROWHEAD BELOW
    '\u0356',  # COMBINING RIGHT ARROWHEAD AND UP ARROWHEAD BELOW
    '\u0357',  # COMBINING RIGHT HALF RING ABOVE
    '\u0358',  # COMBINING DOT ABOVE RIGHT
    '\u0359',  # COMBINING ASTERISK BELOW
    '\u035a',  # COMBINING DOUBLE RING BELOW
    '\u035b',  # COMBINING ZIGZAG ABOVE
    '\u0363',  # COMBINING LATIN SMALL LETTER A
    '\u0364',  # COMBINING LATIN SMALL LETTER E
    '\u0365',  # COMBINING LATIN SMALL LETTER I
    '\u0366',  # COMBINING LATIN SMALL LETTER O
    '\u0367',  # COMBINING LATIN SMALL LETTER U
    '\u0368',  # COMBINING LATIN SMALL LETTER C
    '\u0369',  # COMBINING LATIN SMALL LETTER D
    '\u036a',  # COMBINING LATIN SMALL LETTER H
    '\u036b',  # COMBINING LATIN SMALL LETTER M
    '\u036c',  # COMBINING LATIN SMALL LETTER R
    '\u036d',  # COMBINING LATIN SMALL LETTER T
    '\u036e',  # COMBINING LATIN SMALL LETTER V
    '\u036f',  # COMBINING LATIN SMALL LETTER X
)

SPACE = (
    '\u0020',  # SPACE
    '\u00a0',  # NO-BREAK SPACE
    '\u2002',  # EN SPACE
    '\u2003',  # EM SPACE
    '\u2004',  # THREE-PER-EM SPACE
    '\u2005',  # FOUR-PER-EM SPACE
    '\u2006',  # SIX-PER-EM SPACE
    '\u2007',  # FIGURE SPACE
    '\u2008',  # PUNCTUATION SPACE
    '\u2009',  # THIN SPACE
    '\u200a',  # HAIR SPACE
    '\u200b',  # ZERO WIDTH SPACE
    '\u202f',  # NARROW NO-BREAK SPACE
    '\u205f',  # MEDIUM MATHEMATICAL SPACE
    '\u3000',  # IDEOGRAPHIC SPACE
    '\ufeff',  # ZERO WIDTH NO-BREAK SPACE
)

EQUAL = (
    '\u003d',  # EQUALS SIGN
    '\u2243',  # ASYMPTOTICALLY EQUAL TO
    '\u2245',  # APPROXIMATELY EQUAL TO
    '\u2248',  # ALMOST EQUAL TO
    '\u224a',  # ALMOST EQUAL OR EQUAL TO
    '\u2251',  # GEOMETRICALLY EQUAL TO
    '\u2252',  # APPROXIMATELY EQUAL TO OR THE IMAGE OF
    '\u2253',  # IMAGE OF OR APPROXIMATELY EQUAL TO
    '\u2254',  # COLON EQUALS
    '\u2255',  # EQUALS COLON
    '\u2256',  # RING IN EQUAL TO
    '\u2257',  # RING EQUAL TO
    '\u225b',  # STAR EQUALS
    '\u225c',  # DELTA EQUAL TO
    '\u225d',  # EQUAL TO BY DEFINITION
    '\u225f',  # QUESTIONED EQUAL TO
    '\u22cd',  # REVERSED TILDE EQUALS
    '\u2a66',  # EQUALS SIGN WITH DOT BELOW
    '\u2a6e',  # EQUALS WITH ASTERISK
    '\u2a6f',  # ALMOST EQUAL TO WITH CIRCUMFLEX ACCENT
    '\u2a70',  # APPROXIMATELY EQUAL OR EQUAL TO
    '\u2a73',  # EQUALS SIGN ABOVE TILDE OPERATOR
    '\u2a74',  # DOUBLE COLON EQUAL
    '\u2a75',  # TWO CONSECUTIVE EQUALS SIGNS
    '\u2a76',  # THREE CONSECUTIVE EQUALS SIGNS
    '\u2a77',  # EQUALS SIGN WITH TWO DOTS ABOVE AND TWO DOTS BELOW
    '\u2aae',  # EQUALS SIGN WITH BUMPY ABOVE
    '\uff1d',  # FULLWIDTH EQUALS SIGN
)


def __run_asserts():
    from itertools import combinations, chain
    from unicodedata import bidirectional

    # There must not be repeated
    for key, val in CONFUSABLES.items():
        assert len(val) == len(set(val)), f'repeated in {key}'

    # There should not be the same characters in different groups
    for key_a, key_b in combinations(CONFUSABLES, 2):
        val_a = set(CONFUSABLES[key_a])
        val_b = set(CONFUSABLES[key_b])
        error = f'conflict in {key_a} <> {key_b}'
        assert not val_a.intersection(val_b), error

    # Use only characters for writing from left to right (LTR)
    for char in chain(INVISIBLE, COMBINING, SPACE, EQUAL, *CONFUSABLES.values()):
        code = '\\u{:0>4s}'.format(hex(ord(char)).lstrip('0x'))
        error = f'right-to-left script (RTL): {code}'
        # https://stackoverflow.com/a/17685399/2430102
        assert bidirectional(char) not in ('R', 'AL'), error


def __print_all_confusables(sep=' ', with_code=False):
    char = '{}\u00a0{:0>4s}' if with_code else '{}'
    for val in CONFUSABLES.values():
        chars = (char.format(c, hex(ord(c)).lstrip('0x')) for c in val)
        print(sep.join(chars))
        print()


def __get_code(char):
    return '{:0>4}'.format(hex(ord(char)).lstrip('0x'))


def __test_combining(lst):
    # lst: INVISIBLE, SPACE, EQUAL, CONFUSABLES[OPERATORS]
    for char in lst:
        print(__get_code(char) + ':')
        rows = []
        for com in COMBINING:
            rows.append(' {}{} {}'.format(char, com, __get_code(com)))
        print('   '.join(rows) + '\n')


def __test_captcha():
    captcha, answer, answers = get_captcha(6)
    print(' '.join(__get_code(char) for char in captcha))
    print('{}  {}  {}'.format(captcha, answer, answers))


# ----------------------------------- #


def get_combining(probability):
    if probability:
        nulls = [''] * int(100 / float(probability) - 1)
        return random.choice((random.choice(COMBINING), *nulls))
    return ''


def get_confusable(obj, comb_prob):
    result = []
    for character in str(obj):
        result.append(random.choice(CONFUSABLES[character]))
        result.append(get_combining(comb_prob))
    return ''.join(result)


def get_space(comb_prob, smin=2, smax=3):
    num = random.randint(smin, smax)
    spaces = ''
    # \ufeff: ZERO WIDTH NO-BREAK SPACE
    while len(spaces) < num or re.match('^\ufeff+$', spaces):
        spaces += random.choice(SPACE)
    if comb_prob:
        return ''.join(space + get_combining(comb_prob) for space in spaces)
    return spaces


def get_invisible(comb_prob):
    return random.choice(INVISIBLE) + get_combining(comb_prob)


def get_equal(comb_prob):
    return random.choice(EQUAL) + get_combining(comb_prob)


def get_captcha_in_unicode(*items):
    comb_prob = 66
    chars = []

    chars.append(get_space(0, smin=1, smax=1))

    for item in items:
        chars.append(get_space(comb_prob))
        chars.append(get_invisible(comb_prob))
        chars.append(get_confusable(item, comb_prob))

    chars.append(get_space(0, smin=1, smax=1))

    chars.append(get_space(comb_prob))
    chars.append(get_equal(comb_prob))
    chars.append(get_space(comb_prob))

    chars.append(get_space(0, smin=1, smax=1))

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
    captcha = get_captcha_in_unicode(num_a, operator_sym, num_b)

    # Add fake answers
    correct_answer = str(int(answer))
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


if __name__ == '__main__':
    __run_asserts()
