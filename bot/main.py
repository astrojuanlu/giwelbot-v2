# -*- coding: UTF-8 -*-
# Copyright (C) 2019 Schmidt Cristian Hernán
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
from telegram.error import TelegramError

from spam import is_spam
from debug import flogger
from tools import (get_user_name, get_user_mention, run_async, get_token,
                   change_seed, remove_diacritics, time_to_text, chunked,
                   SECRET_PHRASE, DATE_FMT)
from context import Contextualizer
from captcha import get_captcha
from database import (CaptchaStatus, CaptchaLocation, BASE, User, Chat,
                      Admission, Captcha, Restriction, Expulsion)


DATETIME_IN_LOG = int(os.environ.get('DATETIME_IN_LOG', 1))
DEBUG_CHAT_ID = int(os.environ['DEBUG_CHAT_ID'])
ENV_DATABASE = os.environ['ENV_DATABASE']  # for heroku 'DATABASE_URL'
TOKEN = os.environ['TELEGRAM_TOKEN']
PORT = int(os.environ.get('PORT', 443))
HOST = os.environ['HOST']
BIND = os.environ['BIND']


CAPTCHA_TIMER = datetime.timedelta(minutes=5)
CAPTCHA_TIMER_TEXT = time_to_text(CAPTCHA_TIMER)

GREETING_TIMER = datetime.timedelta(minutes=10)
GREETING_TIMER_TEXT = time_to_text(GREETING_TIMER)

TEMPORARY_RESTRICTION = datetime.timedelta(minutes=15)  # for share media
TEMPORARY_RESTRICTION_TEXT = time_to_text(TEMPORARY_RESTRICTION)

BANNED_RESTRICTION = datetime.timedelta(hours=2)  # for attempts to join
BANNED_RESTRICTION_TEXT = time_to_text(BANNED_RESTRICTION)

DELTA_DELETE_ADMISSIONS = datetime.timedelta(days=1)
# 90 * DELTA_DELETE_ADMISSIONS to delete Expulsion

SPAM_STRIKES_LIMIT = 3


TLD = (r'(?i:com|net|io|me|org|red|info|tools|mobi|xyz|biz|pro|blog|zip|link|to|kim|'
       r'review|country|cricket|science|work|party|g[dql]|jobs|c[co]|i[en]|ly|name)')
URL_MAIL = r'(?P<I>(?i:[ωw]+\.|[/@]))?WORD\.(?(I)WORD|TLD)'
URL_MAIL = URL_MAIL.replace('WORD', r'[^\s.]+').replace('TLD', TLD)
URL_MAIL_SEARCH = re.compile(URL_MAIL).search
INVISIBLE = '\u2061\u2062\u2063\u2064'
SPACE = ('\u0020\u00a0\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a'
         '\u202f\u205f\u3000\u200b\ufeff')
NOVIS = INVISIBLE + SPACE
FAKE_NAME = (r'(?i:cuenta\s*eliminada|deleted\s*account|marketing|website|promo\s*'
             r'agent|telegram|tg(vip)?member|^[\sNOVIS]*$)').replace('NOVIS', NOVIS)
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
               f'en {BANNED_RESTRICTION_TEXT}.')
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


DTL = '%(asctime)s.%(msecs)03d ' if DATETIME_IN_LOG else ''
LOGFMT = f'{DTL}%(levelname)-8s %(threadName)-10s %(name)-9s %(lineno)-4d %(message)s'
logging.basicConfig(level=logging.DEBUG, format=LOGFMT, datefmt=DATE_FMT)
logger = logging.getLogger(__name__)
context = Contextualizer(ENV_DATABASE, DELTA_DELETE_ADMISSIONS)


class UserRestriction(enum.Enum):
    NONE = 0
    TEMP = 1
    FULL = 2


class MenuStep(enum.IntEnum):
    STOP = ConversationHandler.END
    INIT = 0
    CHAT = 1


class DBDelete(enum.IntFlag):
    USER = 1
    ADMISSION = 2
    RESTRICTION = 4
    EXPULSION = 8
    ADM_RES = ADMISSION | RESTRICTION


KEYBOARD_COMMON = {
    'resize_keyboard': True,
    'one_time_keyboard': True,
}


# ----------------------------------- #
# Auxiliary functions


def get_button(text, data=None, url=None):
    return InlineKeyboardButton(text=text, callback_data=data, url=url)


@flogger
@run_async
def restrict_user(bot, chat_id, user_id, restriction, until=0):

    if restriction is UserRestriction.FULL:
        can_send_messages = False
        can_others = False

    elif restriction is UserRestriction.NONE:
        can_send_messages = True
        can_others = True

    elif restriction is UserRestriction.TEMP:
        can_send_messages = True
        can_others = False

    else:
        raise NotImplementedError(str(restriction))

    parameters = {
        'chat_id': chat_id,
        'user_id': user_id,
        'until_date': until,
        'can_send_messages': can_send_messages,
        'can_send_media_messages': can_others,
        'can_send_other_messages': can_others,
        'can_add_web_page_previews': can_others,
    }
    try:
        result = bot.restrict_chat_member(**parameters)
    except TelegramError as tge:
        result = str(tge)
    logger.info(LOG_MSG_UC, user_id, chat_id, restriction, result)


@flogger
@run_async
def ban_user(bot, chat_id, user_id, reason, until):
    chat = bot.get_chat(chat_id=chat_id)

    all_adm = chat.all_members_are_administrators
    bot_adm = any(adm.user.id == bot.id for adm in chat.get_administrators())

    action = 'can not ban'
    if bot_adm and not all_adm:
        try:
            kicked = chat.kick_member(user_id=user_id, until_date=until)
        except TelegramError as tge:
            reason = str(tge)
        else:
            if kicked:
                action = 'ban by'
            else:
                reason = 'unknown'
                # Not kicked but try to limit it
                restrict_user(bot, chat_id, user_id, UserRestriction.FULL)
    else:
        reason = 'insufficient permissions or not allowed'

    logger.info(LOG_MSG_UC, user_id, chat_id, action, reason)

    # FOR DEBUGGING
    user = bot.get_chat_member(chat_id=chat_id, user_id=user_id).user
    text = f'{action}: {reason}\nchat: {chat.title}\nuser: {user.full_name}'
    bot.send_message(chat_id=DEBUG_CHAT_ID, text=text)


@flogger
def pass_ban_rules(ctx, user_id, user_full_name):
    for rule, reason in BAN_RULES:
        if rule(remove_diacritics(user_full_name or '')):
            until = datetime.datetime.now() + BANNED_RESTRICTION
            ban_user(ctx.bot, ctx.cid, user_id, reason, until)
            delete_from_db(ctx, DBDelete.ADM_RES, user_id=user_id)
            ctx.dbs.add(Expulsion(chat_id=ctx.cid, user_id=user_id,
                                  reason=reason, until=until))
            return False
    return True


@flogger
def send_captcha(ctx, mention, message_id=None):
    change_seed(ctx.cid / 10000 + ctx.uid / 100)

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

    parameters = {'text': CAPTCHA_TEXT.format(mention, html.escape(captcha)),
                  'reply_markup': InlineKeyboardMarkup(rows)}
    if message_id:
        message = ctx.edit(message_id=message_id, **parameters)
    else:
        message = ctx.send(**parameters)
    return correct_token, message.message_id


@flogger
@run_async
def delete_message(bot, chat_id, message_id, text):
    if chat_id and message_id:
        try:
            result = bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.debug('%s, mid=%d deleted: %s', text, message_id, result)
        except TelegramError as tge:
            logger.warning('%s, mid=%d: %s', text, message_id, tge)


@flogger
def get_from_db(ctx, attr, chat_id, user_id):
    if chat_id or user_id:
        return getattr(ctx, f'get_{attr}s')(chat_id=chat_id or ctx.cid,
                                            user_id=user_id or ctx.uid)
    return getattr(ctx, attr)


@flogger
def delete_from_db(ctx, delete, *, chat_id=None, user_id=None):
    if isinstance(delete, DBDelete):
        items = []
    elif isinstance(delete, BASE):
        items = [delete]
        delete = None
    else:
        raise NotImplementedError(f'delete type {type(delete)}')

    if delete:
        #if DBDelete.USER in delete:
        #    items.append(ctx.user)

        if DBDelete.ADMISSION in delete:
            admission = get_from_db(ctx, 'admission', chat_id, user_id)
            items.append(admission)
            if admission:
                items.extend(admission.captchas.values())

        if DBDelete.RESTRICTION in delete:
            items.append(get_from_db(ctx, 'restriction', chat_id, user_id))

        #if DBDelete.EXPULSION in delete:
        #    items.append(get_from_db(ctx, 'expulsion', chat_id, user_id))

    for item in items:
        if item:
            ctx.dbs.delete(item)
            logger.debug('Deleted from db %s', item)


# ----------------------------------- #
# Threads


@flogger
@context
def captcha_thread(ctx):
    # Waiting time is over to solve captcha
    ctx.mem.get(ctx.uid, {}).get('wait', {}).pop(ctx.cid, None)

    # Delete group captcha
    message_id = ctx.admission.group_captcha.message_id
    delete_message(ctx.bot, ctx.cid, message_id, 'delete captcha message')

    # Modify private captcha
    if ctx.admission.private_captcha.status is CaptchaStatus.WAITING:
        message_id = ctx.admission.private_captcha.message_id
        result = bool(ctx.edit(chat_id=ctx.uid,  # private_chat_id is user_id
                               message_id=message_id,
                               text=TIMEOUT_CAPTCHA_TEXT))
        logger.debug(LOG_MSG_U, ctx.uid, 'modified private captcha', result)

    # Need to expulsion?
    status = ctx.admission.group_captcha.status
    if status and status is not CaptchaStatus.SOLVED:
        until = datetime.datetime.now() + BANNED_RESTRICTION
        reason = f'captcha not resolved in time ({status})'
        ban_user(ctx.bot, ctx.cid, ctx.uid, reason, until)
        delete_from_db(ctx, DBDelete.ADM_RES)
        ctx.dbs.add(Expulsion(chat_id=ctx.cid, user_id=ctx.uid,
                              reason=reason, until=until))
        delete_message(ctx.bot, ctx.cid, ctx.admission.join_message_id,
                       'delete service message (new user)')


@flogger
@context
def greeting_thread(ctx):
    # Waiting time is over: greet the users

    names = []
    for admission in ctx.get_admissions(chat_id=ctx.cid):

        if admission.group_captcha.status is not CaptchaStatus.SOLVED:
            continue  # captcha still to be resolved

        uid = admission.user_id
        chatmember = ctx.tgc.get_member(uid)  # can change
        if chatmember.status not in (chatmember.LEFT, chatmember.KICKED):
            # Status can by: CREATOR, ADMINISTRATOR, MEMBER, RESTRICTED
            user = chatmember.user
            if pass_ban_rules(ctx, uid, user.full_name):
                # User must have some name...
                name = get_user_name(user)
                # ...and no one has greeted
                if name and admission.to_greet:
                    names.append(name)
                    logger.debug(LOG_MSG_UC, uid, ctx.cid, 'greet', True)
            else:
                delete_message(ctx.bot, ctx.cid, ctx.admission.join_message_id,
                               'delete service message (new user)')
                delete_from_db(ctx, DBDelete.RESTRICTION, user_id=uid)
        else:
            # `join_message_id` not deleted
            # User is no longer present
            delete_from_db(ctx, DBDelete.RESTRICTION, user_id=uid)

        # `Restriction` is eliminated in group_talk_handler and in expulsions
        delete_from_db(ctx, admission)

    if names:
        sep = ', '
        prev = ctx.chat.prev_greet_users or ''
        num = len(names)
        if prev or num > 1:
            if num == 1:
                text = prev + AND + names[0]
            else:
                text = prev + sep + sep.join(names[:-1]) + AND + names[-1]
            text = GREETING_PLURAL.format(html.escape(text))
        else:
            text = GREETING_SINGULAR.format(html.escape(names[0]))

        # New welcome
        message = ctx.send(text=text)

        # Previous welcome
        delete_message(ctx.bot, ctx.cid, ctx.chat.prev_greet_message_id,
                       'delete previous greeting')

        # Save data
        ctx.chat.prev_greet_users = prev + sep.join(names)
        ctx.chat.prev_greet_message_id = message.message_id
        logger.debug(LOG_MSG_C, ctx.cid, 'send greeting', bool(message))


# ----------------------------------- #
# Handlers


@flogger
@run_async
def help_handler(bot, update):
    chat_id = update.effective_chat.id
    bot.send_message(chat_id=chat_id, text=HELP, parse_mode='HTML')


@flogger
@context
def new_user_handler(ctx):
    new = False
    ban = False
    for new_user in ctx.tgm.new_chat_members:
        uid = new_user.id

        if uid == ctx.bot.id:
            continue  # ignore myself

        # It is not necessary to check the expulsions, because Telegram will
        # not allow entry, and if it allows it is because some administrator
        # enabled it

        if pass_ban_rules(ctx, uid, new_user.full_name):
            if new_user.is_bot:
                continue  # ignore other bots (in multiple inclusions)

            user = ctx.get_user(id=uid)

            # Preventively limited to the user
            restrict_user(ctx.bot, ctx.cid, user.id, UserRestriction.FULL)

            # Sending the captcha to the group
            token, mid = send_captcha(ctx, html.escape(get_user_mention(new_user)))
            logger.debug(LOG_MSG_UC, ctx.cid, user.id, 'send captcha', bool(mid))

            # Start timer
            wait = ctx.job_queue.run_once(captcha_thread,
                                          CAPTCHA_TIMER.total_seconds(),
                                          context=(ctx.tgc, new_user))
            # Save info
            # ... in memory
            ctx.mem.setdefault(user.id, {}).setdefault('wait', {})[ctx.cid] = wait
            # ... in database
            delete_from_db(ctx, DBDelete.ADMISSION, user_id=user.id)
            admission = Admission(join_message_id=ctx.mid,
                                  join_message_date=ctx.date,
                                  user=user,
                                  chat=ctx.chat)
            captcha = Captcha(message_id=mid,
                              status=CaptchaStatus.WAITING,
                              token=token,
                              location=CaptchaLocation.GROUP,
                              admission=admission)
            ctx.dbs.add(admission)
            ctx.dbs.add(captcha)
            new = True
        else:
            ban = True

    if ban:
        # If several users entered together, can not be separated in the
        # service message, decided to erase all because it may contain spam
        delete_message(ctx.bot, ctx.cid, ctx.mid,
                       'delete service message (new user)')

    if new:
        # Throw greeting thread
        ctx.job_queue.run_once(greeting_thread,
                               GREETING_TIMER.total_seconds(),
                               context=(ctx.tgc,))


@flogger
@context
def left_user_handler(ctx):
    # User banned by the bot?
    if ctx.from_bot:
        # Cleaning to avoid spam (by name) in service message
        delete_message(ctx.bot, ctx.cid, ctx.mid,
                       'delete service message (left user)')

    user = ctx.get_user(id=ctx.tgm.left_chat_member.id)

    # Stop captchas timer
    wait = ctx.mem.get(user.id, {}).get('wait', {}).pop(ctx.cid, None)
    if wait:
        wait.schedule_removal()

    admission = ctx.get_admissions(chat_id=ctx.cid, user_id=user.id)
    if admission:
        # Delete group captcha
        message_id = admission.group_captcha.message_id
        delete_message(ctx.bot, ctx.cid, message_id, 'delete captcha message')

        # Modify private captcha
        captcha = admission.private_captcha
        if captcha and captcha.status is not CaptchaStatus.SOLVED:
            result = bool(ctx.edit(chat_id=ctx.uid,  # private_chat_id is user_id
                                   message_id=captcha.message_id,
                                   text=LEAVE_GROUP_CAPTCHA_TEXT))
            logger.debug(LOG_MSG_U, ctx.uid, 'modified private captcha', result)

    # Delete all info
    delete_from_db(ctx, DBDelete.ADM_RES, user_id=user.id)


@flogger
@context
def group_talk_handler(ctx):

    # Spam is not allowed
    if is_spam(ctx.tgm):
        delete_message(ctx.bot, ctx.cid, ctx.mid, 'deleted by spam')
        ctx.user.strikes += 1

        if ctx.user.strikes > SPAM_STRIKES_LIMIT:
            until = datetime.datetime.now() + BANNED_RESTRICTION
            reason = 'spammer'
            ban_user(ctx.bot, ctx.cid, ctx.uid, reason, until)
            delete_from_db(ctx, DBDelete.ADM_RES)
            ctx.user.strikes = 0
            ctx.dbs.add(Expulsion(chat_id=ctx.cid, user_id=ctx.uid,
                                  reason=reason, until=until))
            return

        mention = html.escape(get_user_mention(ctx.tgu))
        ctx.send(text=(f'{mention} borré su mensaje porque contiene spam '
                       f'[strike {ctx.user.strikes} de {SPAM_STRIKES_LIMIT}].'))
        return

    # If can not limit the user (available only for supergroups)
    # must delete their messages until the captcha is resolve
    status = ctx.admission.group_captcha.status
    if status and status is not CaptchaStatus.SOLVED:
        delete_message(ctx.bot, ctx.cid, ctx.mid,
                       'user needs to resolve captcha')
        return

    # Or until run out of time limitation
    if ctx.restriction:
        if datetime.datetime.now() < ctx.restriction.until:
            if not ctx.text or URL_MAIL_SEARCH(ctx.text):
                # Only text allowed at beginning
                delete_message(ctx.bot, ctx.cid, ctx.mid,
                               'temporarily limited user')
                return
        else:
            delete_from_db(ctx, DBDelete.RESTRICTION)
            logger.info(LOG_MSG_UC, ctx.uid, ctx.cid, 'unrestricted', True)

    # Cancel greeting grouping
    if ctx.chat.prev_greet_users:
        ctx.chat.prev_greet_users = None
        ctx.chat.prev_greet_message_id = None
        logger.debug(LOG_MSG_C, ctx.cid, 'group next greeting', False)

    # Greeting given by a member of the group
    if GREET_FROM_MEMBER(ctx.text):
        for admission in ctx.get_admissions(chat_id=ctx.cid):
            admission.to_greet = False
        logger.debug(LOG_MSG_C, ctx.cid, 'next greeting', False)


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
@captcha_handler_answer
def captcha_handler(ctx):
    # Searching for origin
    if ctx.is_group:
        cap = ctx.admission.group_captcha
        if cap.message_id != ctx.mid or cap.status is not CaptchaStatus.WAITING:
            return None  # this captcha is from another user or already resolved
        captcha = cap
        chat_id = ctx.admission.chat_id

    elif ctx.is_private:
        # Search which group the captcha corresponds to
        for admission in ctx.get_admissions(user_id=ctx.uid):
            cap = admission.private_captcha
            if cap.message_id == ctx.mid and cap.status is CaptchaStatus.WAITING:
                captcha = cap
                chat_id = admission.chat_id
                break
        else:
            return None  # the time to be finished

    else:
        return None  # not implemented for channels

    token = ctx.update.callback_query.data or ''
    mention = html.escape(get_user_mention(ctx.tgu))

    # New captcha
    if hmac.compare_digest(token, NEW_CAPTCHA_TOKEN):
        logger.debug(LOG_MSG_U, ctx.uid, 'token', 'new')

        token, mid = send_captcha(ctx, mention, captcha.message_id)
        logger.debug(LOG_MSG_UC, ctx.cid, ctx.uid, 'send captcha', bool(mid))
        captcha.token = token
        return None  # nothing else for now

    # Correct answer
    if captcha.is_correct(token):
        logger.debug(LOG_MSG_U, ctx.uid, 'token', 'correct')

        captcha.status = CaptchaStatus.SOLVED
        text = SOLVED_CAPTCHA_TEXT1.format(mention)

        if ctx.is_private:
            # Modify the captcha of the group as well
            g_captcha = captcha.admission.group_captcha
            g_captcha.status = CaptchaStatus.SOLVED
            ctx.edit(chat_id=chat_id, message_id=g_captcha.message_id, text=text)
            text = SOLVED_CAPTCHA_TEXT2

        ctx.edit(text=text)

        # Accepted but temporarily limited
        until = datetime.datetime.now() + TEMPORARY_RESTRICTION
        delete_from_db(ctx, DBDelete.RESTRICTION, chat_id=chat_id)
        ctx.dbs.add(Restriction(chat_id=chat_id, user_id=ctx.uid, until=until))
        restrict_user(ctx.bot, chat_id, ctx.uid, UserRestriction.TEMP, until)
        return SOLVED_CAPTCHA_ALERT

    # Wrong answer
    logger.debug(LOG_MSG_U, ctx.uid, 'token', 'wrong')
    captcha.status = CaptchaStatus.WRONG
    if ctx.is_group:
        # Link to second opportunity
        url = f't.me/{ctx.bot.username}?start={ctx.tgu.id}'
        parameters = {
            'text': WRONG_CAPTCHA_TEXT1.format(mention),
            'reply_markup': InlineKeyboardMarkup([[
                get_button(CHANCE_CAPTCHA_TEXT, url=url)
            ]]),
        }
    else:
        parameters = {'text': WRONG_CAPTCHA_TEXT2}
    ctx.edit(**parameters)
    return WRONG_CAPTCHA_ALERT


# ----------------------------------- #
# Handlers for interaction in private


@flogger
@context
def menu_handler(ctx):
    now = datetime.datetime.now()

    wrongs = {}
    for admission in ctx.get_admissions(user_id=ctx.uid):
        still_valid = now - admission.join_message_date < CAPTCHA_TIMER
        wrong_group = admission.group_captcha.status is CaptchaStatus.WRONG
        not_private = not admission.private_captcha.status
        if still_valid and wrong_group and not_private:
            title = html.escape(admission.chat.title)
            wrongs[f'{len(wrongs)+1}• {title}'] = admission.chat_id
    if wrongs:
        ctx.mem.setdefault(ctx.uid, {})['menu'] = wrongs
        keyboard = ReplyKeyboardMarkup([[YES, NO]], **KEYBOARD_COMMON)
        message = ctx.send(text=START_MENU_TEXT1, reply_markup=keyboard)
        logger.debug(LOG_MSG_P, ctx.uid, 'start menu', bool(message))
        return MenuStep.INIT

    waits = set()
    for expulsion in ctx.get_expulsions(user_id=ctx.uid):
        wait = expulsion.until - now
        if wait.total_seconds() > 0:
            waits.add('• {}{}"{}"'.format(time_to_text(wait),
                                          FOR,
                                          html.escape(expulsion.chat.title)))
    if waits:
        text = START_MENU_TEXT2.format('\n'.join(sorted(waits)))
        keyboard = ReplyKeyboardRemove()
        message = ctx.send(text=text, reply_markup=keyboard)
        logger.debug(LOG_MSG_P, ctx.uid, 'must wait', bool(message))
        return MenuStep.STOP

    ctx.send(text=('No tienes pendiente ningún captcha, '
                   'con /help tienes información adicional.'))
    return MenuStep.STOP


@flogger
@context
def init_handler(ctx):
    wrongs = ctx.mem.get(ctx.uid, {}).get('menu')
    if wrongs:
        if len(wrongs) > 1:
            keyboard = ReplyKeyboardMarkup([[key] for key in wrongs],
                                           **KEYBOARD_COMMON)
            message = ctx.send(text=INIT_MENU_TEXT1, reply_markup=keyboard)
            logger.debug(LOG_MSG_P, ctx.uid, 'select chat', bool(message))
            return MenuStep.CHAT

        key = list(wrongs)[0]
        ctx.send(text=INIT_MENU_TEXT2.format(key),
                 reply_markup=ReplyKeyboardRemove())
        return chat_process(ctx, key)

    ctx.send(text='Ocurrió algún error, vuelva a iniciar el proceso con /start',
             reply_markup=ReplyKeyboardRemove())
    return stop_process(ctx)


@flogger
@context
def chat_handler(ctx):
    key = ctx.text
    ctx.send(text=CHAT_MENU_TEXT.format(html.escape(key)),  # can be modified
             reply_markup=ReplyKeyboardRemove())
    return chat_process(ctx, key)


@flogger
def chat_process(ctx, key):
    chat_id = ctx.mem.get(ctx.uid, {}).get('menu').get(key)
    if chat_id:
        ctx.mem.get(ctx.uid, {}).pop('menu', None)

        mention = html.escape(get_user_mention(ctx.tgu))
        token, mid = send_captcha(ctx, mention)
        admission = ctx.get_admissions(chat_id=chat_id, user_id=ctx.uid)
        ctx.dbs.add(Captcha(message_id=mid,
                            status=CaptchaStatus.WAITING,
                            token=token,
                            location=CaptchaLocation.PRIVATE,
                            admission=admission))

        logger.debug(LOG_MSG_P, ctx.uid, 'send captcha', bool(mid))
        return MenuStep.STOP

    return incorrect_process(ctx)


@flogger
@context
def stop_handler(ctx):
    return stop_process(ctx)


@flogger
def stop_process(ctx):
    ctx.mem.get(ctx.uid, {}).pop('menu', None)
    message = ctx.send(text=CANCEL_MENU_TEXT, reply_markup=ReplyKeyboardRemove())
    logger.debug(LOG_MSG_P, ctx.uid, 'cancel menu', bool(message))
    return MenuStep.STOP


@flogger
@context
def incorrect_handler(ctx):
    incorrect_process(ctx)


@flogger
@run_async
def incorrect_process(ctx):
    message = ctx.send(text=INCORRECT_MENU_TEXT)
    logger.debug(LOG_MSG_P, ctx.uid, 'incorrect option', bool(message))


@flogger
@context
def dc_db_handler(ctx):
    if ctx.is_private and ctx.text.split(None, 1)[-1] == SECRET_PHRASE.decode():
        ctx.dbs.close()
        context.dbe.get_session(drop_all_tables=True, create_all_tables=True)
        logger.info('DB: drop all tables')
    else:
        logger.info('SECRET PHRASE: %s', SECRET_PHRASE.decode())


@flogger
@context
def debug_handler(ctx):
    from pprint import pformat

    texts = []
    for model in (User, Chat, Admission, Restriction, Expulsion):
        rows = '\n'.join(f'• {str(row)}' for row in ctx.dbs.query(model).all())
        if rows:
            texts.append(rows)

    logger.debug('DEBUGGING:\n\nMEM:\n%s\n\nDB:\n%s\n',
                 pformat(ctx.mem),
                 '\n\n'.join(texts))


# ----------------------------------- #


def error_handler(bot, update, error):
    text = 'UPDATE  {}  CAUSED ERROR  {}'.format(update, error)
    logger.critical(text)

    # FOR DEBUGGING
    bot.send_message(chat_id=DEBUG_CHAT_ID, text=text)


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

    dis.add_handler(CommandHandler('dc_db', dc_db_handler, Filters.private))
    dis.add_handler(CommandHandler('debug', debug_handler, Filters.private))

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
        logger.info('start in polling mode, clean=%s', clean)
    else:
        # start_webhook: only set webhook if SSL is handled by library
        updater.bot.set_webhook('{}/{}'.format(HOST, TOKEN))
        # cleaning updates is not supported if SSL-termination happens elsewhere
        updater.start_webhook(listen=BIND, port=PORT, url_path=TOKEN)
        logger.info('start in webhook mode')
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
