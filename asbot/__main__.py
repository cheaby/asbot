
from aiogram.utils.executor import start, start_polling

from asbot.bot import BotDispatcher, start_tasks


if __name__ == "__main__":
    start_tasks(BotDispatcher.loop)
    start_polling(BotDispatcher, skip_updates=True)

