###########################
import os
import asyncio
from dotenv import load_dotenv

import re


from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from sqlalchemy.ext.declarative import declarative_base

from code.db.signals import SignalsOperations
from code.db.users import UsersOperations
from code.tg.keyboards import Keyboards
from code.db.subscriptions import SubscriptionsOperations

from aiogram.types import CallbackQuery, User

load_dotenv()

kbd = Keyboards()



telegram_token = str(os.getenv('bot_token'))
channel_id = str(os.getenv('channel'))

DATABASE_URL = os.getenv('database_url')
db_users_op = UsersOperations(DATABASE_URL)

##### DELETE LATER
ADMIN_ID = os.getenv('owner_id')

dp = Dispatcher()

bot = Bot(token=telegram_token,
          default=DefaultBotProperties(
              parse_mode=ParseMode.HTML
          ),
          disable_web_page_preview=True
          )


"""
UTILS functions
"""

async def get_user_settings(user_id):
    try:
        params = await db_users_op.get_user_data(user_id)
        params = {key: value for key, value in params.items() if key != '_sa_instance_state'}
    except:
        params = False
    return params


# ####### CHANNELS ########
#     ############
#        #####

"""
# on adding new bot - correct privacy settings via bot father &
# add bot to channel admins
"""
@dp.channel_post()
async def channel_message_handler(message: Message):

    db_signals = SignalsOperations(DATABASE_URL)

    try:
        text = message.text

        # Разделяем текст по строкам и берем первую строку
        first_line = text.split('\n')[0]

        # Разделяем первую строку по пробелам и берем первое и последнее слово
        words = first_line.split()
        first_word = words[0]
        last_word = words[-1]

        if first_word.lower()[:3] == 'buy':
            await db_signals.upsert_signal({
                "direction": "buy",
                "coin": last_word,
                "channel_id": str(message.chat.id),
            })

        if first_word.lower()[:4] == 'sell':
            await db_signals.upsert_signal({
                "direction": "sell",
                "coin": last_word,
                "channel_id": str(message.chat.id),
            })
    except:
        print('Не удалось обработать сигнал')


# ####### ADMIN ########
#     ############
#        #####


# # Стартовая функция, отправляет сообщение администратору при запуске бота
# async def on_startup():
#     for admin in admin_id:
#         await bot.send_message(
#             chat_id=admin,
#             text='<b>Торговый бот был запущен!</b>',
#             # reply_markup=kbd.single_btn_back_to_main_menu
#             reply_markup=await kbd.admin_menu()
#             )






# ####### USER INTERFACE ########
#     ############
#        #####

"""
stop trade functions
"""

@dp.callback_query(F.data == 'stop_trade')
async def stop_trade_confirmation(message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)

    if params.get('stop_trading'):
        text = 'Вы уверены что хотите включить Торговлю?'
    else:
        text = 'Вы уверены что хотите отключить Торговлю?'

    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.confirm_stop_trade_menu(params)
        )

@dp.callback_query(F.data == 'stop_trade_confirmed')
async def stop_trade_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status =  para.get('stop_trading')
    print(status)

    if not status:
        text = 'Торговля успешно отключена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': True
        }
        print('Otkluchaem torgovlu')

    else:
        text = 'Торговля успешно включена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': False
        }
        print('Vkluchaem torgovlu')
    try:
        await db_users_op.update_user_fields(telegram_id, fields)
    except Exception as e:
        text = 'Сейчас невозможно изменить параметры, попробуйте позднее'

    para = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )




# stop demo functions
@dp.callback_query(F.data == 'stop_demo')
async def stop_demo_confirmation(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)

    if params.get('trade_type') == 'demo':
        text = 'Вы уверены что хотите отключить демо-режим и начать Торговлю на реальном рынке?'
    else:
        text = 'Вы уверены что хотите включить демо-режим?'

    await bot.send_message(
        chat_id=telegram_id,
        text=text,

        reply_markup=await kbd.confirm_stop_demo_menu(params)
        )

#'stop_demo_confirmed'
@dp.callback_query(F.data == 'stop_demo_confirmed')
async def stop_demo_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status = para.get('trade_type')
    print(status)

    if status == 'demo':
        text = 'Демо-режим успешно отключен\n\n🟢 Управление торговлей'
        fields = {
            'trade_type': 'market'
        }

    else:
        text = 'Демо-режим успешно включен\n\n🟢 Управление торговлей'
        fields = {
            'trade_type': 'demo'
        }
    try:
        await db_users_op.update_user_fields(telegram_id, fields)
    except Exception as e:
        text = 'Сейчас невозможно изменить параметры, попробуйте позднее'

    para = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )


# ##################

# Обработчик команды /start и раздела "main_menu"
@dp.message(Command("start"))
# @dp.message()
@dp.callback_query(F.data == 'main_menu')
async def start(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    print(params)
    if not params:
        subscriptions_op = SubscriptionsOperations(DATABASE_URL)
        params = await subscriptions_op.get_all_subscriptions_data()
        await bot.send_message(
            chat_id=telegram_id,
            text=f' 🔒🔒🔒\n\nВы не являетесь зарегистрированным пользователем \n\n🔑🔑🔑'
                 f'\n\nЧтобы продолжить пользоваться торговым ботом необходимо приобрести подписку\n\nСтоимость подписки:'
                 f'\n\n1 МЕСЯЦ - {params.get('1 МЕСЯЦ').get('cost')} 💲USDT'
                 f'\n\n6 МЕСЯЦЕВ - {params.get('6 МЕСЯЦЕВ').get('cost')} 💲USDT'
                 f'\n\n1 ГОД - {params.get('1 ГОД').get('cost')} 💲USDT'
                 f'\n\nНАВСЕГДА - {params.get('НАВСЕГДА').get('cost')} 💲USDT'
                 f'\n\nВыбрать подписку:',
            reply_markup=await kbd.buy_subscription(params)
        )
        return




###### ОБРАБОТЧИКИ ПОДПИСОК
@dp.callback_query(F.data.in_(['one_month', 'six_month', 'one_year', 'forewer']))
async def handle_subscription(callback_query):
    telegram_id = callback_query.from_user.id

    # Извлечение значения callback_data
    action = callback_query.data
    subscriptions_op = SubscriptionsOperations(DATABASE_URL)
    # params = await subscriptions_op.get_all_subscriptions_data()

    params = {
        'subs': action,
    }

    # print(params)

    await bot.send_message(
        chat_id=telegram_id,
        text='Инструкция по оплате\n\n\n\n\n\n'
             '\n\nПосле оплаты нажмите кнопку ОПЛАЧЕНО',
        reply_markup=await kbd.confirm_payment(params)
    )

@dp.callback_query(F.data.in_(['one_month_conf', 'six_month_conf', 'one_year_conf', 'forewer_conf']))
async def confirm_subscription(callback_query):
    telegram_id = callback_query.from_user.id
    name = f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}'

    # Извлечение значения callback_data
    action = callback_query.data
    subscriptions_op = SubscriptionsOperations(DATABASE_URL)
    params = await subscriptions_op.get_all_subscriptions_data()

    if action == 'one_month':
        subs = params.get('1 МЕСЯЦ')
    if action == 'six_month':
        subs = params.get('6 МЕСЯЦЕВ')
    if action == 'one_year':
        subs = params.get('1 ГОД')
    if action == 'forewer':
        subs = params.get('НАВСЕГДА')

    params = {
        'subs': 'пусто',
    }

    await bot.send_message(
        chat_id=telegram_id,
        text='Проверяем оплату, обычно это занимает несколько минут.'
    )

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f'Юзер {name} c id {telegram_id} запрашивает подверждение оплаты. Подтвердить? ЗДЕСЬ КНОПКИ ПОДВЕРЖДЕНИЯ И ОТПРАВКА ЮЗЕРУ',
        reply_markup=await kbd.admin_payment_confirmation(params)
    )



F.text.regexp(r'Hello, .+')
@dp.callback_query(F.data.startswith('confirmed'))
async def confirmed_payment(message: types.Message):
    telegram_id = message.from_user.id

    #### telegram_id = message.from_user.id
    await bot.send_message(
        chat_id=telegram_id,
        text='ИЗМЕНИТЬ В БАЗЕ.  ПОЗДРАВЛЯЕМ ОПЛАТА ПРОШЛА'
    )

    await bot.send_message(
        chat_id=ADMIN_ID,
        text='ИЗМЕНИТЬ В БАЗЕ. ПОДПИСКА ЮЗЕРА ПОДВЕРЖДЕНА'
    )



# ##############################################

import os
import asyncio
from dotenv import load_dotenv

import re


from aiogram import Bot, Dispatcher, types, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from sqlalchemy.ext.declarative import declarative_base

from code.db.signals import SignalsOperations
from code.db.users import UsersOperations
from code.tg.keyboards import Keyboards
from code.db.subscriptions import SubscriptionsOperations

from aiogram.types import CallbackQuery, User

load_dotenv()

kbd = Keyboards()



telegram_token = str(os.getenv('bot_token'))
channel_id = str(os.getenv('channel'))

DATABASE_URL = os.getenv('database_url')
db_users_op = UsersOperations(DATABASE_URL)

##### DELETE LATER
ADMIN_ID = os.getenv('owner_id')

dp = Dispatcher()

bot = Bot(token=telegram_token,
          default=DefaultBotProperties(
              parse_mode=ParseMode.HTML
          ),
          disable_web_page_preview=True
          )


"""
UTILS functions
"""

async def get_user_settings(user_id):
    try:
        params = await db_users_op.get_user_data(user_id)
        params = {key: value for key, value in params.items() if key != '_sa_instance_state'}
    except:
        params = False
    return params


# ####### CHANNELS ########
#     ############
#        #####

"""
# on adding new bot - correct privacy settings via bot father &
# add bot to channel admins
"""
@dp.channel_post()
async def channel_message_handler(message: Message):

    db_signals = SignalsOperations(DATABASE_URL)

    try:
        text = message.text

        # Разделяем текст по строкам и берем первую строку
        first_line = text.split('\n')[0]

        # Разделяем первую строку по пробелам и берем первое и последнее слово
        words = first_line.split()
        first_word = words[0]
        last_word = words[-1]

        if first_word.lower()[:3] == 'buy':
            await db_signals.upsert_signal({
                "direction": "buy",
                "coin": last_word,
                "channel_id": str(message.chat.id),
            })

        if first_word.lower()[:4] == 'sell':
            await db_signals.upsert_signal({
                "direction": "sell",
                "coin": last_word,
                "channel_id": str(message.chat.id),
            })
    except:
        print('Не удалось обработать сигнал')


# ####### ADMIN ########
#     ############
#        #####


# # Стартовая функция, отправляет сообщение администратору при запуске бота
# async def on_startup():
#     for admin in admin_id:
#         await bot.send_message(
#             chat_id=admin,
#             text='<b>Торговый бот был запущен!</b>',
#             # reply_markup=kbd.single_btn_back_to_main_menu
#             reply_markup=await kbd.admin_menu()
#             )






# ####### USER INTERFACE ########
#     ############
#        #####

"""
stop trade functions
"""

@dp.callback_query(F.data == 'stop_trade')
async def stop_trade_confirmation(message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)

    if params.get('stop_trading'):
        text = 'Вы уверены что хотите включить Торговлю?'
    else:
        text = 'Вы уверены что хотите отключить Торговлю?'

    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.confirm_stop_trade_menu(params)
        )

@dp.callback_query(F.data == 'stop_trade_confirmed')
async def stop_trade_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status =  para.get('stop_trading')
    print(status)

    if not status:
        text = 'Торговля успешно отключена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': True
        }
        print('Otkluchaem torgovlu')

    else:
        text = 'Торговля успешно включена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': False
        }
        print('Vkluchaem torgovlu')
    try:
        await db_users_op.update_user_fields(telegram_id, fields)
    except Exception as e:
        text = 'Сейчас невозможно изменить параметры, попробуйте позднее'

    para = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )




# stop demo functions
@dp.callback_query(F.data == 'stop_demo')
async def stop_demo_confirmation(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)

    if params.get('trade_type') == 'demo':
        text = 'Вы уверены что хотите отключить демо-режим и начать Торговлю на реальном рынке?'
    else:
        text = 'Вы уверены что хотите включить демо-режим?'

    await bot.send_message(
        chat_id=telegram_id,
        text=text,

        reply_markup=await kbd.confirm_stop_demo_menu(params)
        )

#'stop_demo_confirmed'
@dp.callback_query(F.data == 'stop_demo_confirmed')
async def stop_demo_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status = para.get('trade_type')
    print(status)

    if status == 'demo':
        text = 'Демо-режим успешно отключен\n\n🟢 Управление торговлей'
        fields = {
            'trade_type': 'market'
        }

    else:
        text = 'Демо-режим успешно включен\n\n🟢 Управление торговлей'
        fields = {
            'trade_type': 'demo'
        }
    try:
        await db_users_op.update_user_fields(telegram_id, fields)
    except Exception as e:
        text = 'Сейчас невозможно изменить параметры, попробуйте позднее'

    para = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )


# ##################

# Обработчик команды /start и раздела "main_menu"
@dp.message(Command("start"))
# @dp.message()
@dp.callback_query(F.data == 'main_menu')
async def start(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    print(params)
    if not params:
        subscriptions_op = SubscriptionsOperations(DATABASE_URL)
        params = await subscriptions_op.get_all_subscriptions_data()
        params['new_user_id'] = telegram_id
        print(params)
        await bot.send_message(
            chat_id=telegram_id,
            text=f' 🔒🔒🔒\n\nВы не являетесь зарегистрированным пользователем \n\n🔑🔑🔑'
                 f'\n\nЧтобы продолжить пользоваться торговым ботом необходимо приобрести подписку\n\nСтоимость подписки:'
                 f'\n\n1 МЕСЯЦ - {params.get('1 МЕСЯЦ').get('cost')} 💲USDT'
                 f'\n\n6 МЕСЯЦЕВ - {params.get('6 МЕСЯЦЕВ').get('cost')} 💲USDT'
                 f'\n\n1 ГОД - {params.get('1 ГОД').get('cost')} 💲USDT'
                 f'\n\nНАВСЕГДА - {params.get('НАВСЕГДА').get('cost')} 💲USDT'
                 f'\n\nВыбрать подписку:',
            reply_markup=await kbd.buy_subscription(params)
        )
        return




###### ОБРАБОТЧИКИ ПОДПИСОК
@dp.callback_query(F.data.in_(['one_month', 'six_month', 'one_year', 'forewer']))
async def handle_subscription(callback_query):
    telegram_id = callback_query.from_user.id

    # Извлечение значения callback_data
    action = callback_query.data
    subscriptions_op = SubscriptionsOperations(DATABASE_URL)
    # params = await subscriptions_op.get_all_subscriptions_data()

    params = {
        'subs': action,
        'id': telegram_id
    }

    # print(params)

    await bot.send_message(
        chat_id=telegram_id,
        text='Инструкция по оплате\n\n\n\n\n\n'
             '\n\nПосле оплаты нажмите кнопку ОПЛАЧЕНО',
        reply_markup=await kbd.confirm_payment(params)
    )



#@dp.callback_query(F.data.in_(['one_month_conf', 'six_month_conf', 'one_year_conf', 'forewer_conf']))

@dp.callback_query(F.data.startswith('conf_'))
async def confirm_subscription(callback_query):
    telegram_id = callback_query.from_user.id
    name = f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}'

    # Извлечение значения callback_data
    action = callback_query.data
    #subscriptions_op = SubscriptionsOperations(DATABASE_URL)
    #params = await subscriptions_op.get_all_subscriptions_data()

    if 'one_month' in action:
        subs = '1 МЕСЯЦ'
    if 'six_month' in action:
        subs = '6 МЕСЯЦЕВ'
    if 'one_year' in action:
        subs = '1 ГОД'
    if 'forewer' in action:
        subs = 'НАВСЕГДА'

    params = {
        'subs': subs,
        'user_id': telegram_id,
    }
    #print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text='Проверяем оплату, обычно это занимает несколько минут.'
    )

    await bot.send_message(
        chat_id=ADMIN_ID,
        text=f'Юзер {name} c id {telegram_id} запрашивает подверждение оплаты. Подтвердить? ЗДЕСЬ КНОПКИ ПОДВЕРЖДЕНИЯ И ОТПРАВКА ЮЗЕРУ',
        reply_markup=await kbd.admin_payment_confirmation(params)
    )



#F.text.regexp(r'Hello, .+')
@dp.callback_query(F.data.startswith('confirmed'))
async def confirmed_payment(callback_query):
    telegram_id = callback_query.from_user.id
    action = callback_query.data
    parts = action.split("_")
    subs = parts[1]
    user_id = parts[2]


    #### telegram_id = message.from_user.id
    await bot.send_message(
        chat_id=user_id,
        text='ИЗМЕНИТЬ В БАЗЕ.  ПОЗДРАВЛЯЕМ ОПЛАТА ПРОШЛА'
    )

    await bot.send_message(
        chat_id=telegram_id,
        text=f'ИЗМЕНИТЬ В БАЗЕ. ПОДПИСКА ЮЗЕРА ПОДВЕРЖДЕНА\n\n\n'
             f'user_id={user_id}\n'
             f'подписка = {subs}'
    )



# ##############################################

async def start_bot():

    await bot.delete_webhook(drop_pending_updates=True)
    #dp.startup.register(on_startup)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(start_bot())