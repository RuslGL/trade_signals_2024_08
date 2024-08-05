import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

owner_id = int(os.getenv('owner_id'))
telegram_token = str(os.getenv('bot_token'))
channel_id = str(os.getenv('channel'))

dp = Dispatcher()

bot = Bot(token=telegram_token,
          default=DefaultBotProperties(
              parse_mode=ParseMode.HTML
          ),
          disable_web_page_preview=True
          )


# ####### CHANNELS ########
#     ############
#        #####


# on adding new bot - correct privacy settings via bot father &
# add bot to channel admins
@dp.channel_post()
async def message_handler(message: Message):

    ### try/except
    text = message.text

    # Разделяем текст по строкам и берем первую строку
    first_line = text.split('\n')[0]

    # Разделяем первую строку по пробелам и берем первое и последнее слово
    words = first_line.split()
    first_word = words[0]
    last_word = words[-1]

    print(first_word, last_word)

    await message.answer(first_word)


# @dp.message()
# async def echo(message: types.Message):
#     print(message.json())
#     await message.answer(message.text)

# ####### ADMIN ########
#     ############
#        #####


# ####### ON START ########
#     ############
#        #####


# ####### USERS ########
#     ############
#        #####



# ##############################################

async def start_bot():

    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(start_bot())