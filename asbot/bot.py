
from uuid import uuid4

from asyncio import AbstractEventLoop, get_event_loop, sleep
from datetime import datetime, timedelta

from asbot.db import Users

from asbot.log import log

from asbot.config import (
    db_path,

    token,
    qiwi_token,
    channel_pass_id,

    payment_theme,
    payment_currency,

    start_text,
    start_button_text, info_button_text,

    select_plan_products, select_plan_format, select_plan_text,

    payment_proceed_text,
    payment_success_text,

    info_subscriptions_text,

    expiried_text
)

from pyqiwip2p import AioQiwiP2P
from pyqiwip2p.notify import AioQiwiNotify
from pyqiwip2p.p2p_types import Bill

from aiogram import (
    Bot,
    Dispatcher,
    types)
from aiogram.types import CallbackQuery, Message, ContentType
from aiogram.dispatcher import FSMContext
from aiogram.types.reply_keyboard import KeyboardButton, ReplyKeyboardMarkup
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

############
# DATABASE #
############

db = Users(db_path)

########
# QIWI #
########

p2p = AioQiwiP2P(qiwi_token)

QiwiNotifier = AioQiwiNotify(qiwi_token)

#######
# BOT #
#######
bot = Bot(token=token, parse_mode="HTML")

storage = MemoryStorage()

BotDispatcher = Dispatcher(
    bot,
    loop=get_event_loop(),
    storage=storage)


class Forms(StatesGroup):
    start = State()
    plan = State()
    info = State()
    payment = State()


@BotDispatcher.message_handler(state="*", commands=['start'])
async def cmd_start(message: Message, *args):

    await Forms.start.set()

    await bot.send_message(
        chat_id=message.from_user.id,
        text=start_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=start_button_text),
                    KeyboardButton(text=info_button_text)
                ],
            ],
            resize_keyboard=True
        )
    )


#################
# START HANDLER #
#################


@BotDispatcher.message_handler(state=Forms.start, text=start_button_text)
async def start_button_callback(message: Message, *args):
    """Go to select plan panel

    Send a new message to user where he/she can select subscription
    """
    await Forms.plan.set()

    # values "days", "name", "amount" and "description" must be passed in "select_plan_products", but if not,
    # default values will be used instead and user will get wrong representation of subscription menu.
    _fmt_list = "\n".join(
        [
            select_plan_format.format(
                name=k,
                days=v.get("days", 0),
                amount=v.get("amount", 0),
                description=v.get("description", "No description")
            ) for k, v in select_plan_products.items()
        ]
    )

    await bot.send_message(
        chat_id=message.from_user.id,
        text=select_plan_text % _fmt_list,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=k) for k in select_plan_products.keys()]
            ],
            resize_keyboard=True
        )
    )


@BotDispatcher.message_handler(state=Forms.start, text=info_button_text)
async def info_button_callback(message: Message, *args):
    """Go to subscription info

    Send a new message to user where he/she can check their subscription
    """
    await Forms.info.set()

    await bot.send_message(
        chat_id=message.from_user.id,
        text=info_subscriptions_text,
    )


#########################
# PLAN SELECT & PAYMENT #
#########################


@BotDispatcher.message_handler(lambda m: m.text in select_plan_products, state=Forms.plan)
async def select_plan_handler(message: Message, *args):

    _bill_id = "%d_%s" % (message.from_user.id, uuid4())

    _plan_name = message.text
    _message_user_id = message.from_user.id

    _plan = select_plan_products.get(_plan_name, {})
    _amount = _plan.get("amount", 0)

    await Forms.payment.set()

    async with p2p:
        _bill = await p2p.bill(
            _bill_id,
            amount=_amount,
            currency=payment_currency,
            comment=_plan_name,
            theme_code=payment_theme
        )

    await bot.send_message(
        chat_id=message.from_user.id,
        text=payment_proceed_text.format(
            url=_bill.pay_url,
            amount=_amount,
            comment=_message_user_id,
        ),
    )


@BotDispatcher.message_handler(state='*', content_types=ContentType.ANY)
async def clear(message: types.Message, *args):
    await message.delete()


@QiwiNotifier.handler(lambda b: b.status == "PAID")
async def handle_bills(bill: Bill):

    _bill_id: str = str(bill.bill_id)
    log.info("Bot fetched paid bill: %s" % _bill_id)

    _user_id_raw: str = _bill_id.split('_')[0]

    # if user paid not through the bot somehow
    if not _user_id_raw.isdigit():
        log.error("Got invalid bill id: %s" % bill.bill_id)
        return

    _user_id = int(_user_id_raw)

    # fetch plan name and plan data
    _plan_name = bill.comment
    _plan_data = select_plan_products.get(_plan_name, {})

    _plan_days = _plan_data.get("days", 0)

    # apply subscription for this person
    await db.apply_subscription(
        _user_id,
        _plan_days,
        _plan_days == -1)
    log.info("Applied subscription for %d, expiries after %d" % (_user_id, _plan_days))

    # create invite link for this person
    _exp_date = datetime.now() + timedelta(days=1)
    _invite_link = await bot.create_chat_invite_link(
        chat_id=channel_pass_id,
        expire_date=_exp_date,
        member_limit=1
    )

    # send invite link and success message
    await bot.send_message(
        _user_id,
        payment_success_text.format(url=_invite_link)
    )


async def create_table():
    log.info("Creating database for users")
    await db.create()


async def handle_expiried():
    while True:
        log.info("Looking for expiried subscriptions every hour")

        for value in await db.get_expiried():
            user_id = value[0]

            log.info("Notify user %d about expiried sub." % user_id)
            await db.discard_subscription(user_id)
            await bot.send_message(user_id, expiried_text)
            await bot.kick_chat_member(channel_pass_id, user_id)
            await sleep(1)

        await sleep(3600)


def start_tasks(loop: AbstractEventLoop):
    loop.run_until_complete(create_table())
    loop.create_task(handle_expiried())
    loop.create_task(QiwiNotifier.a_start(port=8000))


__all__ = (
    "BotDispatcher", "start_tasks"
)
