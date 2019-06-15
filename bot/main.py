# -*- coding: UTF-8 -*-
'''Telegram bot for welcome.'''

import sys
assert sys.hexversion > 0x03070000, 'requires python 3.7 or higher'
# Use: hmac.digest(key, msg, digest)

import os
import re
import enum
import hmac
import html
import logging
import argparse
import datetime
import functools

from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, Filters, ConversationHandler,
                          CallbackQueryHandler, RegexHandler,
                          CommandHandler, MessageHandler)
from telegram.error import BadRequest

from debug import flogger
from tools import (run_async, get_token, change_seed, remove_diacritics,
                   time_to_text, chunked)
from context import Contextualizer
from captcha import get_captcha

TOKEN = os.environ['TELEGRAM_TOKEN']
PORT = int(os.environ['PORT'])
HOST = 'https://test-welcome-tg-bot.herokuapp.com'
BIND = '0.0.0.0'


CAPTCHA_TIMER = 5 * 60  # seconds
CAPTCHA_TIMER_TEXT = time_to_text(CAPTCHA_TIMER)

GREETING_TIMER = 10 * 60  # seconds
GREETING_TIMER_TEXT = time_to_text(GREETING_TIMER)

TEMPORARY_RESTRICTION = datetime.timedelta(minutes=15)  # for share media
TEMPORARY_RESTRICTION_TEXT = time_to_text(TEMPORARY_RESTRICTION)

ATTEMPT_INTERVAL = datetime.timedelta(hours=1)  # for attempts to join
ATTEMPT_INTERVAL_TEXT = time_to_text(ATTEMPT_INTERVAL)


TLD = (r'(?i:com|net|io|me|org|red|info|tools|mobi|xyz|biz|pro|blog|zip|link|to|kim|'
       r'review|country|cricket|science|work|party|g[dql]|jobs|c[co]|i[en]|ly|name)')
URL_MAIL = r'(?P<I>(?i:[ωw]+\.|[/@]))?WORD\.(?(I)WORD|TLD)'
URL_MAIL = URL_MAIL.replace('WORD', r'[^\s.]+').replace('TLD', TLD)
URL_MAIL_SEARCH = re.compile(URL_MAIL).search
INVISIBLE = '\u2061\u2062\u2063\u2064'
SPACE = ('\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u202f'
         '\u205f\u3000\ufeff')
NOVIS = INVISIBLE + SPACE
FAKE_NAME = (r'(?i:cuenta\s*eliminada|deleted\s*account|marketing|website|promo\s*'
             r'agent|telegram|tgmember|^[\sNOVIS]*$)').replace('NOVIS', NOVIS)
BAN_RULES = (
    (lambda name: len(name) > 39, 'long name'),
    (URL_MAIL_SEARCH, 'name with uri'),
    (re.compile(FAKE_NAME).search, 'fake name'),
)
LOG_MSG_UC = 'user=%d in chat=%d %s: %s'
LOG_MSG_C = 'chat=%d %s: %s'
LOG_MSG_U = 'user=%d %s: %s'
LOG_MSG_P = '[private] user=%d %s: %s'

GREET_FROM_MEMBER = re.compile('[bv]ien[vb]enid|welcome', re.IGNORECASE).search


FOR = ' para '
AND = ' y '
YES = 'Si'
NO = 'No'

GREETING_SINGULAR = ('¡Te damos la bienvenida {}! '
                     'En el mensaje anclado están las reglas básicas del grupo.')
GREETING_PLURAL = ('¡Les damos la bienvenida {}! '
                   'En el mensaje anclado están las reglas básicas del grupo.')

NEW_CAPTCHA_TEXT = 'Obtener otro captcha'
NEW_CAPTCHA_TOKEN = get_token()
CHANCE_CAPTCHA_TEXT = 'Chat privado'
CAPTCHA_TEXT = ('Por favor {} resuelve el siguiente captcha '
                '(una simple operación matemática):\n\n{}\n\nResultado:')
SOLVED_CAPTCHA_TEXT1 = ('✅ Captcha correcto {}. '
                        'Ahora podrá enviar solo texto sin URLs durante '
                        f'{TEMPORARY_RESTRICTION_TEXT}.')
SOLVED_CAPTCHA_TEXT2 = '✅ Captcha correcto.'
SOLVED_CAPTCHA_ALERT = 'Respuesta correcta'
CAN_NOT_USE = ('No podrá usar el grupo, contacte con un administrador '
               'si considera que es un error. Puede volver a intentar '
               f'en {ATTEMPT_INTERVAL_TEXT}.')
WRONG_CAPTCHA_TEXT1 = ('⛔️ Captcha incorrecto {}. Por privado con '
                       '<code>/start</code> puedes resolver otro captcha.')
WRONG_CAPTCHA_TEXT2 = f'⛔️ Captcha incorrecto. {CAN_NOT_USE}'
WRONG_CAPTCHA_ALERT = 'Respuesta incorrecta'
TIMEOUT_CAPTCHA_TEXT = ('⛔️ Se acabó el tiempo para resolver el captcha. '
                        f'{CAN_NOT_USE}')
LEAVE_GROUP_CAPTCHA_TEXT = f'⛔️ Ya no es miembro de este grupo. {CAN_NOT_USE}'


START_MENU_TEXT1 = '¿Desea resolver un captcha?'
START_MENU_TEXT2 = ('Tiene grupos con captchas mal resueltos, '
                    'pero debe esperar para reintentar:\n{}')
INIT_MENU_TEXT1 = ('Elija el grupo para resolver el captcha. '
                   'Puede detener el proceso con /cancel.')
INIT_MENU_TEXT2 = 'Procesando {}'
CHAT_MENU_TEXT = 'Procesando {}'
CANCEL_MENU_TEXT = 'Operación cancelada, puede volver a empezar con /start.'
INCORRECT_MENU_TEXT = 'Opción incorrecta, reintente (use el teclado).'


HELP = ('<b>Bot de bienvenida</b>\n\n'
        'Las bienvenidas son agrupadas en caso de no haber actividad en el grupo '
        'y no son dadas si otra persona lo hace antes, '
        f'para lo cual se cuenta con un timeout de {GREETING_TIMER_TEXT}.\n\n'
        'Además se cuentan con algunas reglas básicas anti-spammer '
        'basadas en el nombre del usuario y en un sistema de captchas.\n\n'
        f'Un usuario aceptado tendrá que esperar {TEMPORARY_RESTRICTION_TEXT} '
        'para poder compartir audios, documentos, fotos, videos, GIF, stickers '
        'y previsualizaciones de páginas web.\n\n'
        '<b>Nota:</b> el bot elimina sistemáticamente los captchas que envía, '
        'como así también los mensajes de servicio de los usuarios baneados. '
        'Para poder realizar estas funciones el bot debe ser administrador.')


DATEFMT = '%Y%m%d %H%M%S'
LOGFMT = ('%(asctime)s.%(msecs)03d %(levelname)-8s %(threadName)-10s '
          '%(lineno)-4d %(name)-9s %(message)s')
logging.basicConfig(level=logging.DEBUG, format=LOGFMT, datefmt=DATEFMT)
logger = logging.getLogger(__name__)
context = Contextualizer()


class UserRestriction(enum.Enum):
    NONE = 0
    TEMP = 1
    FULL = 2


class MenuStep(enum.IntEnum):
    STOP = ConversationHandler.END
    INIT = 0
    CHAT = 1


class CaptchaStatus(enum.Enum):
    WAITING = 0
    SOLVED = 1
    WRONG = 2


KEYBOARD_COMMON = {
    'resize_keyboard': True,
    'one_time_keyboard': True,
}


# ----------------------------------- #
# Auxiliary functions


def assert_keys(key_names):
    def wrapper(func):
        @functools.wraps(func)
        def wrapped(ctx):
            current_keys = ctx.mem.get_keys()
            expected_keys = [getattr(ctx, key) for key in key_names.split()]
            assert current_keys == expected_keys, (f'{func.__module__} '
                                                   f'{current_keys} != '
                                                   f'{expected_keys}')
            return func(ctx)
        return wrapped
    return wrapper


def get_mention_html(user):
    full_name = user.full_name
    username = user.username

    if full_name and username:
        mention = '{} (@{})'.format(full_name, username)
    elif full_name:
        mention = '{}'.format(full_name)
    elif username:
        mention = '@{}'.format(username)
    else:
        mention = '{}'.format(user.id)

    return html.escape(mention)


def get_button(text, data=None, url=None):
    return InlineKeyboardButton(text=text, callback_data=data, url=url)


@flogger
@run_async
def send_help(bot, chat_id):
    bot.send_message(chat_id=chat_id, text=HELP, parse_mode='HTML')


@flogger
@run_async
def restrict_user(bot, chat_id, user_id, restriction):

    if restriction is UserRestriction.FULL:
        can_send_messages = False
        can_others = False
        until_date = 0  # forever

    elif restriction is UserRestriction.NONE:
        can_send_messages = True
        can_others = True
        until_date = 0  # forever

    elif restriction is UserRestriction.TEMP:
        can_send_messages = True
        can_others = False
        until_date = datetime.datetime.now() + TEMPORARY_RESTRICTION

    else:
        raise NotImplementedError(str(restriction))

    parameters = {
        'chat_id': chat_id,
        'user_id': user_id,
        'until_date': until_date,
        'can_send_messages': can_send_messages,
        'can_send_media_messages': can_others,
        'can_send_other_messages': can_others,
        'can_add_web_page_previews': can_others,
    }
    try:
        result = bot.restrict_chat_member(**parameters)
    except BadRequest as exc:
        result = str(exc)
    logger.info(LOG_MSG_UC, user_id, chat_id, restriction, result)


@flogger
@run_async
def ban_user(chat, user, reason):

    all_adm = chat.all_members_are_administrators
    bot_adm = any(m.user.id == chat.bot.id for m in chat.get_administrators())

    if bot_adm and not all_adm:
        until_date = datetime.datetime.now() + ATTEMPT_INTERVAL
        kicked = chat.kick_member(user.id, until_date=until_date)
        if kicked:
            action = 'ban by'
        else:
            action = 'can not ban'
            reason = 'unknown'
            # Not kicked but try to limit it
            restrict_user(chat.bot, chat.id, user.id, UserRestriction.FULL)
    else:
        action = 'can not ban'
        reason = 'insufficient permissions or not allowed'

    logger.info(LOG_MSG_UC, user.id, chat.id, action, reason)

    # FOR DEBUGGING
    text = f'{action}: {reason}\nchat: {chat.title}\nuser: {user.full_name}'
    chat.bot.send_message(chat_id=-1001332763908, text=html.escape(text))


@flogger
def pass_ban_rules(chat, user):
    for rule, reason in BAN_RULES:
        if rule(remove_diacritics(user.full_name or '')):
            ban_user(chat, user, reason)
            return False
    return True


@flogger
def send_captcha(chat, user, message=None):
    change_seed(chat.id / 10000 + user.id / 10)

    captcha, correct_answer, answers = get_captcha(num_answers=6)
    rows = []
    for row in [answers[:3], answers[3:]]:
        cols = []
        for answer in row:
            token = get_token()
            cols.append(get_button(answer, token))
            if answer == correct_answer:
                correct_token = token
        rows.append(cols)

    rows.append([get_button(NEW_CAPTCHA_TEXT, NEW_CAPTCHA_TOKEN)])

    keyboard = InlineKeyboardMarkup(rows)
    text = CAPTCHA_TEXT.format(get_mention_html(user), html.escape(captcha))
    parameters = {'text': text, 'reply_markup': keyboard, 'parse_mode': 'HTML'}
    if message:
        message.edit_text(**parameters)
    else:
        message = chat.send_message(**parameters)
    logger.debug(LOG_MSG_UC, user.id, chat.id, 'send captcha', bool(message))
    return correct_token, message


@flogger
@run_async
def delete_message(message, text):
    try:
        result = message.delete()
        logger.debug('%s, mid=%d deleted: %s', text, message.message_id, result)
    except BadRequest as exc:
        logger.warning('%s, mid=%d: %s', text, message.message_id, exc)
    except AttributeError:
        pass  # can by message == None


# ----------------------------------- #
# Threads


@flogger
@context
@assert_keys('cid uid')
def captcha_thread(ctx):
    # Waiting time is over to solve captcha

    # Delete group captcha
    message = ctx.mem[:, 'captchas', 'group', 'message']
    delete_message(message, 'delete captcha message')

    # Modify private captcha
    if ctx.mem[:, 'captchas', 'private', 'status'] is CaptchaStatus.WAITING:
        message = ctx.mem[:, 'captchas', 'private', 'message']
        if message:
            result = bool(message.edit_text(text=TIMEOUT_CAPTCHA_TEXT))
            logger.debug(LOG_MSG_U, ctx.uid, 'modified private captcha', result)

    # Need to expulsion?
    if ctx.mem[:, 'captchas', 'group', 'status'] is not CaptchaStatus.SOLVED:
        ban_user(ctx.chat, ctx.user, 'captcha not resolved in time')
        delete_message(ctx.mem[:, 'join'], 'delete service message (new user)')
        del ctx.mem[:, 'join']
        del ctx.mem[:, 'greet']
        del ctx.mem[:, 'restrict']

    # Delete all captchas
    del ctx.mem[:, 'captchas']
    ctx.mem.delete_if_empty()


@flogger
@context
@assert_keys('cid')
def greeting_thread(ctx):
    # Waiting time is over: greet the users

    user_id_list = []
    names_list = []
    for user_id in ctx.mem.user_ids():

        if ctx.mem[:, user_id, 'captchas']:
            continue  # captcha still to be resolved

        chatmember = ctx.chat.get_member(user_id)  # can change in time
        if chatmember.status not in (chatmember.LEFT, chatmember.KICKED):
            # status can by: CREATOR, ADMINISTRATOR, MEMBER, RESTRICTED
            user = chatmember.user
            if pass_ban_rules(ctx.chat, user):
                # users must have first_name, last_name or username to be greeted
                name = user.first_name or user.last_name or user.username or None
                # ...and no one has greeted
                if name and ctx.mem[:, user_id, 'greet']:
                    names_list.append(name)
                    logger.debug(LOG_MSG_UC, user_id, ctx.cid, 'greet', True)
            else:
                message = ctx.mem[:, user_id, 'join']
                delete_message(message, 'delete service message (new user)')
                del ctx.mem[:, user_id, 'restrict']
        else:
            # user is no longer present
            del ctx.mem[:, user_id, 'restrict']

        # 'restrict' is eliminated in group_talk_handler (and in the expulsions)
        user_data = ctx.mem[:, user_id:{}]
        user_data.pop('join', None)
        user_data.pop('greet', None)
        user_id_list.append(user_id)

    # `ctx.mem.delete_if_empty` can modify the list of users (`ctx.mem.user_ids`)
    for user_id in user_id_list:
        ctx.mem.delete_if_empty(ctx.cid, user_id)

    if names_list:
        names_list = ctx.mem[:, 'previous', 'names':[]] + names_list
        if len(names_list) > 1:
            names = ', '.join(names_list[:-1]) + AND + names_list[-1]
            text = GREETING_PLURAL.format(html.escape(names))
        else:
            text = GREETING_SINGULAR.format(html.escape(names_list[0]))

        message = ctx.chat.send_message(text=text)

        delete_message(ctx.mem[:, 'previous', 'message'], 'delete previous greeting')

        ctx.mem[:, 'previous'] = {'names': names_list, 'message': message}
        logger.debug(LOG_MSG_C, ctx.cid, 'send greeting', bool(message))


# ----------------------------------- #
# Handlers


@flogger
def help_handler(bot, update):
    send_help(bot, update.effective_chat.id)


@flogger
@context
@assert_keys('cid uid')
def new_user_handler(ctx):
    ban = False
    new = False
    for new_user in ctx.message.new_chat_members:

        if new_user.id == ctx.bot.id:
            continue  # ignore myself

        ctx.mem.mod_key(1, new_user.id)

        if pass_ban_rules(ctx.chat, new_user):

            if new_user.is_bot:
                continue  # ignore other bots

            # Preventively limited to the user
            restrict_user(ctx.bot, ctx.cid, new_user.id, UserRestriction.FULL)

            # Sending the message with the captcha to the group
            captcha_token, captcha_message = send_captcha(ctx.chat, new_user)
            # Start timer
            wait = ctx.job_queue.run_once(captcha_thread,
                                          CAPTCHA_TIMER,
                                          context=(ctx.chat, new_user))
            # Save info
            ctx.mem[:] = {
                'join': ctx.message,
                'greet': True,
                'restrict': None,
                'captchas': {
                    'wait': wait,
                    'group': {
                        'message': captcha_message,
                        'status': CaptchaStatus.WAITING,
                        'token': captcha_token,
                    },
                    'private': {},
                },
            }
            new = True
        else:
            ban = True

    if ban:
        # If several users entered together, can not be separated in the
        # service message, decided to erase all because it may contain spam
        delete_message(ctx.message, 'delete service message (new user)')

    if new:
        # Throw greeting thread
        wait = ctx.job_queue.run_once(greeting_thread,
                                      GREETING_TIMER,
                                      context=(ctx.chat,))


@flogger
@context
@assert_keys('cid uid')
def left_user_handler(ctx):
    # User banned by the bot?
    if ctx.from_bot:
        # Cleaning to avoid spam in name
        delete_message(ctx.message, 'delete service message (left user)')

    ctx.mem.mod_key(1, ctx.message.left_chat_member.id)
    # User can be before the bot...
    # ...or bot might not have been operational when he left
    if ctx.mem.contains_keys():

        # Stop captchas timer
        wait = ctx.mem[:, 'captchas', 'wait']
        if wait:
            wait.schedule_removal()

        # Delete group captcha
        message = ctx.mem[:, 'captchas', 'group', 'message']
        delete_message(message, 'delete captcha message')

        # Modify private captcha
        message = ctx.mem[:, 'captchas', 'private', 'message']
        if message:
            result = bool(message.edit_text(text=LEAVE_GROUP_CAPTCHA_TEXT))
            logger.debug(LOG_MSG_U, ctx.uid, 'modified private captcha', result)

        # Delete all info
        del ctx.mem[:]
        ctx.mem.delete_if_empty()


@flogger
@context
@assert_keys('cid uid')
def group_talk_handler(ctx):
    if ctx.from_bot:
        return

    # Cancel greeting grouping
    if ctx.mem[ctx.cid, 'previous']:
        del ctx.mem[ctx.cid, 'previous']
        logger.debug(LOG_MSG_C, ctx.cid, 'group next greeting', False)

    # Greeting given by a member of the group
    if GREET_FROM_MEMBER(ctx.message.text or ''):
        for user_id, info in ctx.mem[ctx.cid:{}].items():
            if isinstance(user_id, int):
                info['greet'] = False
        logger.debug(LOG_MSG_C, ctx.cid, 'next greeting', False)

    # If can not limit the user (available only for supergroups)
    # must delete their messages until the captcha is resolve
    status = ctx.mem[:, 'captchas', 'group', 'status']
    if status is not None and status is not CaptchaStatus.SOLVED:
        delete_message(ctx.message, 'user needs to resolve captcha')

    # Or until run out of time limitation
    restrict = ctx.mem[:, 'restrict']
    if restrict:
        if restrict > datetime.datetime.now():
            if not ctx.message.text or URL_MAIL_SEARCH(ctx.message.text):
                # Only text allowed at beginning
                delete_message(ctx.message, 'temporarily limited user')
        else:
            del ctx.mem[:, 'restrict']
            ctx.mem.delete_if_empty()
            logger.info(LOG_MSG_UC, ctx.uid, ctx.cid, 'unrestricted', True)


def captcha_handler_answer(func):
    @functools.wraps(func)
    def decorator(ctx):
        answer = func(ctx)
        ctx.update.callback_query.answer(answer, show_alert=bool(answer))
        logger.debug(LOG_MSG_UC, ctx.uid, ctx.cid, 'captcha handler', answer)
        return answer
    return decorator


@flogger
@context
@assert_keys('cid uid')
@captcha_handler_answer
def captcha_handler(ctx):
    ctx.mem.add_keys('captchas')

    # Verify identity
    if ctx.is_group:
        ctx.mem.add_keys('group')
        if ctx.mem[:, 'message'] != ctx.message:
            return None  # this captcha is from another user
        chat_id = ctx.cid

    elif ctx.is_private:
        # Search which group the captcha corresponds to.
        ctx.mem.add_keys('private')
        for chat_id in ctx.mem.chat_ids():
            ctx.mem.mod_key(0, chat_id)
            if ctx.mem[:, 'message'] == ctx.message:
                break
        else:
            return None  # time may have run out

    else:
        return None  # not implemented for channels

    # `ctx.chat` can be group or private
    # `chat_id` is from the group always

    token = ctx.update.callback_query.data or ''

    # New captcha
    if hmac.compare_digest(token, NEW_CAPTCHA_TOKEN):
        new_token, _ = send_captcha(ctx.chat, ctx.user, ctx.message)
        ctx.mem[:, 'token'] = new_token
        return None  # nothing else to do

    # Correct answer
    if hmac.compare_digest(token, ctx.mem[:, 'token']):
        ctx.mem[:, 'status'] = CaptchaStatus.SOLVED
        text = SOLVED_CAPTCHA_TEXT1.format(get_mention_html(ctx.user))

        if ctx.is_private:
            # Modify the captcha of the group as well
            ctx.mem.mod_key(3, 'group')
            ctx.mem[:, 'status'] = CaptchaStatus.SOLVED
            ctx.mem[:, 'message'].edit_text(text=text)
            text = SOLVED_CAPTCHA_TEXT2

        ctx.message.edit_text(text=text)
        # Accepted but temporarily limited
        until_date = datetime.datetime.now() + TEMPORARY_RESTRICTION
        ctx.mem[chat_id, ctx.uid, 'restrict'] = until_date
        restrict_user(ctx.bot, chat_id, ctx.uid, UserRestriction.TEMP)
        return SOLVED_CAPTCHA_ALERT

    # Wrong answer
    ctx.mem[:, 'status'] = CaptchaStatus.WRONG
    if ctx.is_group:
        # Link to second opportunity
        parameters = {
            'text': WRONG_CAPTCHA_TEXT1.format(get_mention_html(ctx.user)),
            'parse_mode': 'HTML',
            'reply_markup': InlineKeyboardMarkup([[
                get_button(CHANCE_CAPTCHA_TEXT, url=f't.me/{ctx.bot.username}')
            ]]),
        }
    else:
        parameters = {'text': WRONG_CAPTCHA_TEXT2}
    ctx.message.edit_text(**parameters)
    return WRONG_CAPTCHA_ALERT


# ----------------------------------- #
# Handlers for interaction in private


@flogger
@context
@assert_keys('cid uid')
def menu_handler(ctx):
    ctx.mem.add_keys('captchas')
    wrongs = {}
    waits = []
    for chat_id in ctx.mem.chat_ids():
        ctx.mem.mod_key(0, chat_id)
        message = ctx.mem[:, 'group', 'message']
        if message:
            title = html.escape(message.chat.title)

            wrong_group = ctx.mem[:, 'group', 'status'] is CaptchaStatus.WRONG
            private = ctx.mem[:, 'private', 'status']

            if wrong_group and private is None:
                wrongs[f'{len(wrongs)+1}• {title}'] = chat_id

            elif private is CaptchaStatus.WRONG:
                wait = message.date + ATTEMPT_INTERVAL - datetime.datetime.now()
                waits.append('• {}{}"{}"'.format(time_to_text(wait), FOR, title))

    if wrongs:
        ctx.mem['privates', ctx.uid] = wrongs
        keyboard = ReplyKeyboardMarkup([[YES, NO]], **KEYBOARD_COMMON)
        message = ctx.message.reply_text(text=START_MENU_TEXT1,
                                         reply_markup=keyboard)
        logger.debug(LOG_MSG_P, ctx.uid, 'start menu', bool(message))
        return MenuStep.INIT

    if waits:
        text = START_MENU_TEXT2.format('\n'.join(waits))
        keyboard = ReplyKeyboardRemove()
        message = ctx.message.reply_text(text=text, reply_markup=keyboard)
        logger.debug(LOG_MSG_P, ctx.uid, 'must wait', bool(message))
        return MenuStep.STOP

    send_help(ctx.bot, ctx.cid)
    return MenuStep.STOP


@flogger
@context
@assert_keys('cid uid')
def init_handler(ctx):
    wrongs = ctx.mem['privates', ctx.uid]
    if len(wrongs) > 1:
        keyboard = ReplyKeyboardMarkup([[key] for key in wrongs],
                                       **KEYBOARD_COMMON)
        message = ctx.message.reply_text(text=INIT_MENU_TEXT1,
                                         reply_markup=keyboard)
        logger.debug(LOG_MSG_P, ctx.uid, 'select chat', bool(message))
        return MenuStep.CHAT

    key = list(wrongs)[0]
    ctx.message.reply_text(text=INIT_MENU_TEXT2.format(key),
                           reply_markup=ReplyKeyboardRemove())
    return chat_process(ctx, key)


@flogger
@context
@assert_keys('cid uid')
def chat_handler(ctx):
    key = ctx.message.text or ''
    ctx.message.reply_text(text=CHAT_MENU_TEXT.format(html.escape(key)),
                           reply_markup=ReplyKeyboardRemove())
    return chat_process(ctx, key)


@flogger
def chat_process(ctx, key):
    chat_id = ctx.mem['privates', ctx.uid, key]
    if chat_id:
        del ctx.mem['privates', ctx.uid]

        token, message = send_captcha(ctx.chat, ctx.user)
        ctx.mem[chat_id, ctx.uid, 'captchas', 'private'] = {
            'message': message,
            'status': CaptchaStatus.WAITING,
            'token': token,
        }
        logger.debug(LOG_MSG_P, ctx.uid, 'send captcha', bool(message))
        return MenuStep.STOP

    return incorrect_process(ctx)


@flogger
@context
@assert_keys('cid uid')
def stop_handler(ctx):
    if ctx.mem.contains_keys('privates', ctx.uid):
        del ctx.mem['privates', ctx.uid]

    message = ctx.message.reply_text(text=CANCEL_MENU_TEXT,
                                     reply_markup=ReplyKeyboardRemove())
    logger.debug(LOG_MSG_P, ctx.uid, 'cancel menu', bool(message))
    return MenuStep.STOP


@flogger
@context
@assert_keys('cid uid')
def incorrect_handler(ctx):
    incorrect_process(ctx)


@flogger
@run_async
def incorrect_process(ctx):
    message = ctx.message.reply_text(text=INCORRECT_MENU_TEXT)
    logger.debug(LOG_MSG_P, ctx.uid, 'incorrect option', bool(message))


@flogger
@context
@assert_keys('cid uid')
def debug_handler(ctx):
    from debug import __format
    logger.debug('CTX.MEM.DATA: %s', __format(ctx.mem.get_data()))


# ----------------------------------- #


def error_handler(bot, update, error):
    text = 'UPDATE  {}  CAUSED ERROR  {}'.format(update, error)
    logger.critical(text)

    # FOR DEBUGGING
    bot.send_message(chat_id=-1001332763908, text=text)


def get_handler(data):
    handlers = []
    for pattern, handler in chunked(data, 2):
        handlers.append(RegexHandler(pattern, handler))
    handlers.append(MessageHandler(Filters.text, incorrect_handler))
    return handlers


def main(polling, clean):
    logger.info('Initializing bot...')
    updater = Updater(TOKEN)
    dis = updater.dispatcher

    dis.add_handler(CommandHandler('debug', debug_handler, Filters.all))

    # Group handlers
    dis.add_handler(CommandHandler('start', help_handler, ~Filters.private))
    dis.add_handler(CommandHandler('help', help_handler))

    dis.add_handler(MessageHandler(Filters.status_update.new_chat_members,
                                   new_user_handler,
                                   pass_job_queue=True))
    dis.add_handler(MessageHandler(Filters.status_update.left_chat_member,
                                   left_user_handler))
    dis.add_handler(MessageHandler(Filters.group,
                                   group_talk_handler))

    dis.add_handler(CallbackQueryHandler(captcha_handler))

    # Private handlers
    menu = (
        (MenuStep.INIT, (f'^(?i:{YES})$', init_handler,
                         f'^(?i:{NO})$', stop_handler)),
        (MenuStep.CHAT, (r'^\d+•\s+.+$', chat_handler)),
    )
    dis.add_handler(ConversationHandler(
        entry_points=[CommandHandler('start', menu_handler, Filters.private)],
        states={code: get_handler(data) for code, data in menu},
        fallbacks=[CommandHandler('cancel', stop_handler, Filters.private)],
    ))

    dis.add_error_handler(error_handler)

    # Mode
    if polling:
        updater.start_polling(clean=clean)
        logger.debug('start in polling mode, clean=%s', clean)
    else:
        # start_webhook: only set webhook if SSL is handled by library
        updater.bot.set_webhook('{}/{}'.format(HOST, TOKEN))
        # cleaning updates is not supported if SSL-termination happens elsewhere
        updater.start_webhook(listen=BIND, port=PORT, url_path=TOKEN)
        logger.debug('start in webhook mode')
    # Wait...
    updater.idle()


def run():
    parser = argparse.ArgumentParser(
        description='The default operating mode is webhook',
        epilog='Verbose: 0 WARNING, 1 INFO, 2 DEBUG (only bot); 3 Full DEBUG')
    parser.add_argument(
        '-p', '--polling',
        help='start the bot in polling mode',
        action='store_true')
    parser.add_argument(
        '-c', '--clean',
        help='clean any pending updates',
        action='store_true')
    parser.add_argument(
        '-v', '--verbose',
        help='verbose level, repeat up to three times',
        action='count',
        default=0)
    args = parser.parse_args()

    levels = (logging.WARNING, logging.INFO, logging.DEBUG)
    level = levels[min(len(levels) - 1, args.verbose)]
    logger.setLevel(level)

    if args.verbose < 3:
        # Mute all, show only the bot
        logger_names = (
            'JobQueue',
            'telegram.bot',
            'telegram.ext.updater',
            'telegram.ext.dispatcher',
            'telegram.ext.conversationhandler',
            'telegram.vendor.ptb_urllib3.urllib3.util.retry',
            'telegram.vendor.ptb_urllib3.urllib3.connectionpool',
        )
        for logger_name in logger_names:
            logging.getLogger(logger_name).setLevel(logging.WARNING)

    main(args.polling, args.clean)


if __name__ == '__main__':
    run()
