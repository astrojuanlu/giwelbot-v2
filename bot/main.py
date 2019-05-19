# -*- coding: UTF-8 -*-
'''Telegram bot for welcome.'''

import sys
assert sys.hexversion > 0x03070000, 'requires python 3.5 or higher'

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
from context import Context
from captcha import get_captcha

TOKEN = os.environ['TELEGRAM_TOKEN']
PORT = int(os.environ['PORT'])
HOST = 'https://test-welcome-tg-bot.herokuapp.com'
BIND = '0.0.0.0'


GREETING_TIMER = 1 * 60  # seconds
GREETING_TIMER_TEXT = time_to_text(GREETING_TIMER)

CAPTCHA_TIMER = 1 * 60  # seconds
CAPTCHA_TIMER_TEXT = time_to_text(CAPTCHA_TIMER)

ATTEMPT_INTERVAL = datetime.timedelta(seconds=90)  # for attempts to join
ATTEMPT_INTERVAL_TEXT = time_to_text(ATTEMPT_INTERVAL)

TEMPORARY_RESTRICTION = datetime.timedelta(seconds=90)  # for share media
TEMPORARY_RESTRICTION_TEXT = time_to_text(TEMPORARY_RESTRICTION)


TLD = (r'(?i:com|net|io|me|org|red|info|tools|mobi|xyz|biz|pro|blog|zip|link|to|kim|'
       r'review|country|cricket|science|work|party|g[dql]|jobs|c[co]|i[en]|ly|name)')
URL_MAIL = r'(?P<I>(?i:[ωw]+\.|[/@]))?WORD\.(?(I)WORD|TLD)'
URL_MAIL = URL_MAIL.replace('WORD', r'[^\s.]+').replace('TLD', TLD)
INVISIBLE = '\u2061\u2062\u2063\u2064'
SPACE = ('\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u200b\u202f'
         '\u205f\u3000\ufeff')
NOVIS = INVISIBLE + SPACE
FAKE_NAME = (r'(?i:cuenta\s*eliminada|deleted\s*account|marketing|website|promo\s*'
             r'agent|telegram|tgmember|^[\sNOVIS]*$)').replace('NOVIS', NOVIS)
BAN_RULES = (
    (lambda name: len(name) > 39, 'long name'),
    (re.compile(URL_MAIL).search, 'name with uri'),
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
SOLVED_CAPTCHA_TEXT1 = '✅ Captcha correcto {}.'
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


logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
context = Context()


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


# ----------------------------------- #
# Auxiliary functions


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
        'until_date': until_date,
        'can_send_messages': can_send_messages,
        'can_send_media_messages': can_others,
        'can_send_other_messages': can_others,
        'can_add_web_page_previews': can_others,
    }
    try:
        result = bot.restrict_chat_member(chat_id, user_id, **parameters)
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
def captcha_thread(chat, user, data):
    # Waiting time is over to solve captcha

    # Delete group captcha
    message = data[:, 'captchas', 'group', 'message']
    delete_message(message, 'delete captcha message')

    # Modify private captcha
    if data[:, 'captchas', 'private', 'status'] is CaptchaStatus.WAITING:
        message = data[:, 'captchas', 'private', 'message']
        if message:
            result = message.edit_text(text=TIMEOUT_CAPTCHA_TEXT)
            logger.debug(LOG_MSG_U, user.id, 'modified private captcha', result)

    # Need to expulsion?
    if data[:, 'captchas', 'group', 'status'] is not CaptchaStatus.SOLVED:
        ban_user(chat, user, 'captcha not resolved in time')
        delete_message(data[:, 'join'], 'delete captcha message')
        del data[:, 'join']
        del data[:, 'greet']
        del data[:, 'restrict']

    # Delete all captchas
    del data[:, 'captchas']
    data.delete_if_empty()


@flogger
@context
def greeting_thread(chat, data):
    # Waiting time is over: greet the users

    # Decrement num greeting
    data['greeting'] = data['greeting'] - 1

    names_list = []
    for user_id in data.user_ids():

        if data[:, user_id, 'captchas']:
            continue  # captcha still to be resolved

        chatmember = chat.get_member(user_id)  # can change in time
        if chatmember.status not in (chatmember.LEFT, chatmember.KICKED):
            # status can by: CREATOR, ADMINISTRATOR, MEMBER, RESTRICTED
            user = chatmember.user
            if pass_ban_rules(chat, user):
                # users must have first_name, last_name or username to be greeted
                name = user.first_name or user.last_name or user.username or None
                # ...and no one has greeted
                if name and data[:, user_id, 'greet']:
                    names_list.append(name)
                    logger.debug(LOG_MSG_UC, user_id, chat.id, 'greet', True)
            else:
                message = data[:, user_id, 'join']
                delete_message(message, 'delete service message (new user)')
                del data[:, user_id, 'restrict']
        else:
            # user is no longer present
            del data[:, user_id, 'restrict']

        # 'restrict' is eliminated in group_talk_handler (and in the expulsions)
        del data[:, user_id, 'join']
        del data[:, user_id, 'greet']
        data.delete_if_empty(chat.id, user_id)

    if names_list:
        names_list = data[:, 'previous', 'names':[]] + names_list
        if len(names_list) > 1:
            names = ', '.join(names_list[:-1]) + AND + names_list[-1]
            text = GREETING_PLURAL.format(html.escape(names))
        else:
            text = GREETING_SINGULAR.format(html.escape(names_list[0]))

        message = chat.send_message(text=text)

        delete_message(data[:, 'previous', 'message'], 'delete previous greeting')

        data[:, 'previous'] = {'names': names_list, 'message': message}
        logger.debug(LOG_MSG_C, chat.id, 'send greeting', bool(message))


# ----------------------------------- #
# Handlers


@flogger
def help_handler(bot, update):
    send_help(bot, update.effective_chat.id)


@flogger
@context
def new_user_handler(bot, update, job_queue, chat, data):
    ban = False
    new = False
    for new_user in update.message.new_chat_members:

        if new_user.id == bot.id:
            continue  # ignore myself

        if pass_ban_rules(chat, new_user):

            if new_user.is_bot:
                continue  # ignore other bots

            # Preventively limited to the user
            restrict_user(bot, chat.id, new_user.id, UserRestriction.FULL)

            # Sending the message with the captcha to the group
            captcha_token, captcha_message = send_captcha(chat, new_user)
            # Start timer
            wait = job_queue.run_once(captcha_thread,
                                      CAPTCHA_TIMER,
                                      context=(chat, new_user))
            # Save info
            data[chat.id, new_user.id] = {
                'join': update.message,
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
        delete_message(update.message, 'delete service message (new user)')

    if new:
        # Throw greeting thread
        wait = job_queue.run_once(greeting_thread, GREETING_TIMER, context=(chat,))
        data[chat.id, 'greeting'] = data[chat.id, 'greeting':0] + 1


@flogger
@context
def left_user_handler(bot, update, chat, user, data):
    # User banned by the bot?
    if user.id == bot.id:
        # Cleaning to avoid spam in name
        delete_message(update.message, 'delete service message (left user)')

    data.set_keys(chat.id, update.message.left_chat_member.id)
    # User can be before the bot...
    # ...or bot might not have been operational when he left.
    if data.contains_keys():

        # Stop captchas timer
        wait = data[:, 'captchas', 'wait']
        if wait:
            wait.schedule_removal()

        # Delete group captcha
        message = data[:, 'captchas', 'group', 'message']
        delete_message(message, 'delete captcha message')

        # Modify private captcha
        message = data[:, 'captchas', 'private', 'message']
        if message:
            result = message.edit_text(text=LEAVE_GROUP_CAPTCHA_TEXT)
            logger.debug(LOG_MSG_U, user.id, 'modified private captcha', result)

        # Delete all info
        del data[:]
        data.delete_if_empty()


@flogger
@context
def group_talk_handler(bot, update, chat, user, data):
    if user.id == bot.id:
        return

    if data[chat.id, 'greeting':0] > 0:
        message = update.effective_message

        # Cancel greeting grouping
        if data[chat.id, 'previous']:
            del data[chat.id, 'previous']
            logger.debug(LOG_MSG_C, chat.id, 'group next greeting', False)

        # Greeting given by a member of the group
        if GREET_FROM_MEMBER(message.text or ''):
            for user_id, info in data[chat.id:{}].items():
                if isinstance(user_id, int):
                    info['greet'] = False
            logger.debug(LOG_MSG_C, chat.id, 'next greeting', False)

        # If can not limit the user (available only for supergroups)
        # must delete their messages until the captcha is resolve
        status = data[:, 'captchas', 'group', 'status']
        if status is not None and status is not CaptchaStatus.SOLVED:
            delete_message(message, 'user needs to resolve captcha')

        # Or until run out of time limitation
        restrict = data[:, 'restrict']
        if restrict:
            if restrict + TEMPORARY_RESTRICTION > datetime.datetime.now():
                if not message.text:
                    # Only text allowed at beginning
                    delete_message(message, 'temporarily limited user')
            else:
                del data[:, 'restrict']
                data.delete_if_empty()
                logger.debug(LOG_MSG_UC, user.id, chat.id, 'unrestricted', True)


def captcha_handler_answer(func):
    @functools.wraps(func)
    def decorator(bot, update, chat, user, data):
        answer = func(bot, update, chat, user, data)
        update.callback_query.answer(answer, show_alert=bool(answer))
        logger.debug(LOG_MSG_UC, user.id, chat.id, 'captcha handler', answer)
        return answer
    return decorator


@flogger
@context
@captcha_handler_answer
def captcha_handler(bot, update, chat, user, data):
    message = update.effective_message
    in_group = chat.type in (chat.GROUP, chat.SUPERGROUP)
    in_private = chat.type == chat.PRIVATE

    data.add_keys('captchas')

    # Verify identity
    if in_group:
        data.add_keys('group')
        if data[:, 'message'] != message:
            return None  # this captcha is from another user
        chat_id = chat.id

    elif in_private:
        # Search which group the captcha corresponds to.
        data.add_keys('private')
        for chat_id in data.chat_ids():
            data.mod_key(0, chat_id)
            if data[:, 'message'] == message:
                break
        else:
            return None  # time may have run out

    else:
        return None  # not implemented for channels

    # 'chat' can be group or private
    # 'chat_id' is from the group always

    token = update.callback_query.data or ''

    # New captcha
    if hmac.compare_digest(token, NEW_CAPTCHA_TOKEN):
        new_token, _ = send_captcha(chat, user, message)
        data[:, 'token'] = new_token
        return None  # nothing else to do

    # Correct answer
    if hmac.compare_digest(token, data[:, 'token']):
        data[:, 'status'] = CaptchaStatus.SOLVED
        text = SOLVED_CAPTCHA_TEXT1.format(get_mention_html(user))
        if in_private:
            # Modify the captcha of the group as well
            data.mod_key(3, 'group')
            data[:, 'status'] = CaptchaStatus.SOLVED
            data[:, 'message'].edit_text(text=text)
            text = SOLVED_CAPTCHA_TEXT2
        message.edit_text(text=text)
        # Accepted but temporarily limited
        until_date = datetime.datetime.now() + TEMPORARY_RESTRICTION
        data[chat_id, user.id, 'restrict'] = until_date
        restrict_user(bot, chat_id, user.id, UserRestriction.TEMP)
        return SOLVED_CAPTCHA_ALERT

    # Wrong answer
    data[:, 'status'] = CaptchaStatus.WRONG
    if in_group:
        # Link to second opportunity
        parameters = {
            'text': WRONG_CAPTCHA_TEXT1.format(get_mention_html(user)),
            'parse_mode': 'HTML',
            'reply_markup': InlineKeyboardMarkup([[
                get_button(CHANCE_CAPTCHA_TEXT, url=f't.me/{bot.username}')
            ]]),
        }
    else:
        parameters = {'text': WRONG_CAPTCHA_TEXT2}
    message.edit_text(**parameters)
    return WRONG_CAPTCHA_ALERT


# ----------------------------------- #
# Handlers for interaction in private


@flogger
@context
def menu_handler(bot, update, chat, user, data):
    data.add_keys('captchas')
    wrongs = {}
    waits = []
    for chat_id in data.chat_ids():
        data.mod_key(0, chat_id)

        message = data[:, 'group', 'message']
        title = html.escape(message.chat.title)

        wrong_group = data[:, 'group', 'status'] is CaptchaStatus.WRONG
        private = data[:, 'private', 'status']

        if wrong_group and private is None:
            wrongs[f'{len(wrongs)+1}• {title}'] = chat_id

        elif private is CaptchaStatus.WRONG:
            wait = message.date + ATTEMPT_INTERVAL - datetime.datetime.now()
            waits.append('• {}{}"{}"'.format(time_to_text(wait), FOR, title))

    if wrongs:
        data['privates', user.id] = wrongs
        keyboard = ReplyKeyboardMarkup([[YES, NO]], one_time_keyboard=True)
        message = update.message.reply_text(text=START_MENU_TEXT1,
                                            reply_markup=keyboard)
        logger.debug(LOG_MSG_P, user.id, 'start menu', bool(message))
        return MenuStep.INIT

    if waits:
        text = START_MENU_TEXT2.format('\n'.join(waits))
        keyboard = ReplyKeyboardRemove()
        message = update.message.reply_text(text=text, reply_markup=keyboard)
        logger.debug(LOG_MSG_P, user.id, 'must wait', bool(message))
        return MenuStep.END

    send_help(bot, chat.id)
    return MenuStep.END


@flogger
@context
def init_handler(update, chat, user, data):
    wrongs = data['privates', user.id]
    if len(wrongs) > 1:
        keyboard = ReplyKeyboardMarkup([[key] for key in wrongs],
                                       one_time_keyboard=True)
        message = update.message.reply_text(text=INIT_MENU_TEXT1,
                                            reply_markup=keyboard)
        logger.debug(LOG_MSG_P, user.id, 'select chat', bool(message))
        return MenuStep.CHAT

    key = list(wrongs)[0]
    update.message.reply_text(text=INIT_MENU_TEXT2.format(key),
                              reply_markup=ReplyKeyboardRemove())
    return chat_process(update, chat, user, data, key)


@flogger
@context
def chat_handler(update, chat, user, data):
    key = update.message.text or ''
    update.message.reply_text(text=CHAT_MENU_TEXT.format(html.escape(key)),
                              reply_markup=ReplyKeyboardRemove())
    return chat_process(update, chat, user, data, key)


@flogger
def chat_process(update, chat, user, data, key):
    chat_id = data['privates', user.id, key]
    if chat_id:
        del data['privates', user.id]

        token, message = send_captcha(chat, user)
        data[chat_id, user.id, 'captchas', 'private'] = {
            'message': message,
            'status': CaptchaStatus.WAITING,
            'token': token,
        }
        logger.debug(LOG_MSG_P, user.id, 'send captcha', bool(message))
        return MenuStep.END

    return incorrect_process(update)


@flogger
@context
def stop_handler(update, user, data):
    if data.contains_keys('privates', user.id):
        del data['privates', user.id]

    message = update.message.reply_text(text=CANCEL_MENU_TEXT,
                                        reply_markup=ReplyKeyboardRemove())
    logger.debug(LOG_MSG_P, user.id, 'cancel menu', bool(message))
    return MenuStep.END


@flogger
@run_async
def incorrect_handler(_bot, update):
    incorrect_process(update)


@flogger
def incorrect_process(update):
    user_id = update.message.from_user.id
    message = update.message.reply_text(text=INCORRECT_MENU_TEXT)
    logger.debug(LOG_MSG_P, user_id, 'incorrect option', bool(message))


# ----------------------------------- #


def error_handler(bot, update, error):
    text = 'UPDATE  {}  CAUSED ERROR  {}'.format(update, error)
    logger.critical(text)

    # FOR DEBUGGING
    bot.send_message(chat_id=-1001332763908, text=html.escape(text))


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
        # Mute telegram (show only bot)
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
