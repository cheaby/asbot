
from uuid import uuid4

from asyncio import AbstractEventLoop, get_event_loop, sleep
from datetime import datetime, timedelta

from asbot.db import Users, UserModel

from asbot.log import log

from asbot.config import (
    db_path,

    token,
    qiwi_token,
    channel_pass_id,

    payment_theme,
    payment_currency,

    home_button_text,

    before_start_text,

    start_text,
    start_button_text, info_button_text,

    select_plan_products,
    select_plan_format,
    select_plan_text,

    payment_check_text,
    payment_notyet_text,
    payment_cancel_text,
    payment_proceed_text,
    payment_success_text,
    payment_expiried_text,
    payment_canceled_text,

    info_subscriptions_text,
    info_subscriptions_nosub,
    info_subscriptions_format,
    info_subscription_forever,

    expiried_text
)

from pyqiwip2p import AioQiwiP2P
from pyqiwip2p.notify import AioQiwiNotify
from pyqiwip2p.p2p_types import Bill

from aiogram import (
    Bot,
    Dispatcher,
    types)
from aiogram.types import Message, ContentType
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


@BotDispatcher.message_handler(state="*", commands=["id"])
async def resolve_channel_id(message: Message, *_args):
    await message.reply(message.chat.id)


@BotDispatcher.message_handler(state="*", commands=["start"])
async def start(message: Message, *args):
    _user_id: int = message.from_user.id

    await db.register_user(_user_id)

    await bot.send_message(
        chat_id=_user_id,
        text=before_start_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text=home_button_text)
                ],
            ],
            resize_keyboard=True
        )
    )


@BotDispatcher.message_handler(state="*", text=home_button_text)
async def menu(message: Message, state: FSMContext, *args):
    """Show start menu

    Show start menu, start menu can be invoked in every state by clicking button "home"
    """

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
    _fmt_list: str = "\n".join(
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
                [KeyboardButton(text=k) for k in select_plan_products.keys()],
                [KeyboardButton(text=home_button_text)]
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

    _sub: str = info_subscriptions_nosub
    _spent: int = 0

    _user_id: int = message.from_user.id
    _user_name: str = message.from_user.username
    _user_data: UserModel = await db.get_user_data(_user_id)

    if _user_data:
        _is_inf: bool = _user_data.is_infinity
        _expdate_raw: str = _user_data.expdate

        if _expdate_raw:
            _d: datetime = datetime.strptime(_expdate_raw, "%Y-%m-%d %H:%M:%S.%f")
            _sub = info_subscriptions_format.format(
                expdate=_d.strftime("%d.%m.%Y")
            ) if not _is_inf else info_subscription_forever

        _spent = _user_data.spent

    await bot.send_message(
        chat_id=_user_id,
        text=info_subscriptions_text.format(
            sub=_sub,
            spent=_spent,
            username=_user_name
        ),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=home_button_text)]
            ],
            resize_keyboard=True
        )
    )


#########################
# PLAN SELECT & PAYMENT #
#########################


@BotDispatcher.message_handler(lambda m: m.text in select_plan_products, state=Forms.plan)
async def select_plan_handler(message: Message, state: FSMContext, *args):
    """Go to plan select

    Show menu where user can select their subscription plan
    """
    await Forms.payment.set()

    _bill: Bill

    _pl_name: str = message.text
    _user_id: int = message.from_user.id
    _bill_id: str = f"{_user_id}_{uuid4()}"
    _plan_data: dict = select_plan_products.get(_pl_name, {})
    _plan_amount: int = _plan_data.get("amount", 0)

    async with state.proxy() as _dt:
        _dt["bill_id"] = _bill_id
        _dt["plan_data"] = _plan_data

    async with AioQiwiP2P(qiwi_token) as p2p:
        _bill = await p2p.bill(
            _bill_id,
            amount=_plan_amount,
            currency=payment_currency,
            comment=_pl_name,
            theme_code=payment_theme
        )

    await bot.send_message(
        chat_id=message.from_user.id,
        text=payment_proceed_text.format(
            url=_bill.pay_url,
            amount=_plan_amount,
            comment=_user_id,
        ),
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=payment_check_text)],
                [KeyboardButton(text=payment_cancel_text)]
            ],
            resize_keyboard=True
        )
    )


@BotDispatcher.message_handler(state=Forms.payment, text=payment_cancel_text)
async def payment_canceled(message: Message, state: FSMContext, *args):

    async with state.proxy() as data:
        async with AioQiwiP2P(qiwi_token) as p2p:
            await p2p.reject(data["bill_id"])

    await bot.send_message(
        chat_id=message.from_user.id,
        text=payment_canceled_text,
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=home_button_text)]
            ],
            resize_keyboard=True
        )
    )


@BotDispatcher.message_handler(state=Forms.payment, text=payment_check_text)
async def payment_check(message: Message, state: FSMContext, *args):

    _message: str
    _message_rkm = None
    _user_id: int = message.from_user.id

    async with state.proxy() as data:
        async with AioQiwiP2P(qiwi_token) as p2p:
            _bill = await p2p.check(data["bill_id"])

            match _bill.status:

                case "PAID":
                    _inlink = await bot.create_chat_invite_link(
                        chat_id=channel_pass_id,
                        expire_date=datetime.now() + timedelta(days=1),
                        member_limit=1
                    )
                    _message = payment_success_text.format(
                        url=_inlink.invite_link
                    )
                    _message_rkm = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text=home_button_text)]
                        ],
                        resize_keyboard=True
                    )
                    _plan: dict = data["plan_data"]
                    _plan_days: int = _plan["days"]
                    _plan_amount: int = _plan["amount"]
                    await db.apply_subscription(
                        _user_id,
                        _plan_days,
                        _plan_days == -1,
                        _plan_amount
                    )

                case "WAITING":
                    _message = payment_notyet_text

                case "EXPIRIED":
                    _message = payment_expiried_text
                    _message_rkm = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text=home_button_text)]
                        ],
                        resize_keyboard=True
                    )

    await bot.send_message(
        chat_id=message.from_user.id,
        text=_message,
        reply_markup=_message_rkm
    )


@BotDispatcher.message_handler(state='*', content_types=ContentType.ANY)
async def clear(message: types.Message, *args):
    """Clear chat

    Clear user messages after they typed something
    """
    await message.delete()


async def create_table():
    log.info("Creating database for users")
    await db.create()


async def handle_expiried():
    while True:
        log.info("Looking for expiried subscriptions every hour")

        for value in await db.get_expiried():
            _user_id: int = value[0]

            log.info(f"Notify user {_user_id} about expiried sub.")
            await db.discard_subscription(_user_id)
            await bot.send_message(_user_id, expiried_text)
            await bot.kick_chat_member(channel_pass_id, _user_id)
            await sleep(1)

        await sleep(3600)


def start_tasks(loop: AbstractEventLoop):
    loop.run_until_complete(create_table())
    loop.create_task(handle_expiried())


__all__ = (
    "BotDispatcher", "start_tasks"
)
