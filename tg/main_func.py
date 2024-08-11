import time
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta

from aiogram import F

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

from code.api.account import find_start_budget

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


@dp.callback_query(F.data == 'admin_menu')
async def start_admin_menu(callback_query):

    telegram_id = callback_query.from_user.id
    print(telegram_id )
    print(ADMIN_ID)
    params = await get_user_settings(telegram_id)
    print(params)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return
    await bot.send_message(
        chat_id=telegram_id,
        text="Админ меню",
        reply_markup=await kbd.admin_menu()
    )







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
        if not params.get('main_secret_key') or not params.get('main_api_key'):
            await bot.send_message(
                chat_id=telegram_id,
                text="🛑🛑🛑"
                     "\nОтсутствуют действующие API ключи"
                     "\n\n🔐🔐🔐"
                     "\nОтправьте следующим сообщением API key"
                     "\n\n 📌📌📌"
                     "\n<b>Сообщение начните фразой api key</b>,"
                     "\n🔴🔴🔴"
                     "\n\nПРИМЕР:"
                     "\napi key rtyvuA8WFFgjyuHv25"

            )
            return
    else:
        text = 'Вы уверены что хотите отключить Торговлю?'

    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.confirm_stop_trade_menu(params)
        )

@dp.message(F.text.lower().startswith('api key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    #print(message.text.lower())
    api_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    await user_op.update_user_fields(telegram_id, {'main_api_key': api_key})
    # сразу сохранитьы
    await bot.send_message(
        chat_id=telegram_id,
        text="API KEY успешно получен и сохранен"
             "\nОсталось отправить SECRET KEY"
             "\n\n🔐🔐🔐"
             "\nОтправьте следующим сообщением SECRET KEY"
             "\n\n 📌📌📌"
             "\n<b>Сообщение начните фразой secret key</b>,"
             "\n🔴🔴🔴"
             "\n\nПРИМЕР:"
             "\nsecret key rtyvuA8WFFgjyuHv25rtyvuA8WFFgjyuHv25rtyvuA8WFFgjyuHv25"
    )

@dp.message(F.text.lower().startswith('secret key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    secret_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    await user_op.update_user_fields(telegram_id, {'main_secret_key': secret_key})

    ##### проверка работоспособности ключей через запрос баланса
    check = await find_start_budget(telegram_id)
    print(check)
    if check == -1:
        print('invalid keys')
        await user_op.update_user_fields(telegram_id, {'main_secret_key': None})
        await bot.send_message(
            chat_id=telegram_id,

            text="🔴Получены недействительные API ключи"
                 "\n\n🔴Проверьте, что вы отправили правильные данные, "
                 "\n\n🔴проверьте настройки ключей,"
                 "\n\n🔴при необходимости создайте новые ключи."
                 "\n\n🔐🔐🔐 После этого попробуйте отправить ключи заново",
            reply_markup=await kbd.main_menu(params)
        )
        return

    # сразу сохранить и проверить запросом баланса
    await bot.send_message(
        chat_id=telegram_id,
        text="SECRET KEY успешно получен и сохранен, теперь вы можете активировать режим торговли",
        reply_markup=await kbd.main_menu(params)
    )




@dp.callback_query(F.data == 'stop_trade_confirmed')
async def stop_trade_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status =  para.get('stop_trading')
    # print(status)

    if not status:
        text = 'Торговля успешно отключена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': True
        }
        # print('Otkluchaem torgovlu')

    else:
        text = 'Торговля успешно включена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': False
        }
        # print('Vkluchaem torgovlu')
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
    # print(status)

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

    if not params:
        subscriptions_op = SubscriptionsOperations(DATABASE_URL)
        params = await subscriptions_op.get_all_subscriptions_data()
        params['new_user_id'] = telegram_id
        # print(params)
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

    #user_op = UsersOperations(DATABASE_URL)
    params = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text='🟢 Управление торговлей',
        reply_markup=await kbd.main_menu(params)
    )
    return



###### ОБРАБОТЧИКИ ПОДПИСОК

@dp.callback_query(F.data.in_(['manage_subscription']))
async def mange_subscription(callback_query):
    telegram_id = callback_query.from_user.id
    subscriptions_op = SubscriptionsOperations(DATABASE_URL)
    params = await subscriptions_op.get_all_subscriptions_data()
    params['new_user_id'] = telegram_id
    user_subs = (await get_user_settings(telegram_id)).get('subscription')
    # print(user_subs)

    user_subs = datetime.fromtimestamp(user_subs, tz=timezone.utc)
    current_datetime = datetime.now(timezone.utc)

    # Вычисление разницы между двумя датами
    delta = user_subs - current_datetime

    # Вычисление разницы в днях
    days = delta.days
    # print(days)
    if days >= 0:
        txt = f'До окончания действия подписки осталось дней {days}'
    else:
        txt = 'У вас нет действующей подписки!'

    await bot.send_message(
        chat_id=telegram_id,
        text=f' {txt} 🔑🔑🔑'
             f'\n\nЕсли вы хотите продлить срок пользования торговым ботом, необходимо приобрести подписку\n'
             f'\n\n1 МЕСЯЦ - {params.get('1 МЕСЯЦ').get('cost')} 💲USDT'
             f'\n\n6 МЕСЯЦЕВ - {params.get('6 МЕСЯЦЕВ').get('cost')} 💲USDT'
             f'\n\n1 ГОД - {params.get('1 ГОД').get('cost')} 💲USDT'
             f'\n\nНАВСЕГДА - {params.get('НАВСЕГДА').get('cost')} 💲USDT'
             f'\n\nВыбрать подписку:',
        reply_markup=await kbd.buy_subscription(params)
    )


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



@dp.callback_query(F.data.startswith('conf_'))
async def confirm_subscription(callback_query):
    telegram_id = callback_query.from_user.id
    name = f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}'

    # Извлечение значения callback_data
    action = callback_query.data

    if 'one_month' in action:
        subs = '1 МЕСЯЦ'
    if 'six_month' in action:
        subs = '6 МЕСЯЦЕВ'
    if 'one_year' in action:
        subs = '1 ГОД'
    if 'forewer' in action:
        subs = 'НАВСЕГДА'

    name = f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}'

    params = {
        'username': name,
        'telegram_id': int(telegram_id),
    }

    user_op = UsersOperations(DATABASE_URL)
    await user_op.upsert_user(params)

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
        text=f'Юзер {name} c id {telegram_id} запрашивает подверждение оплаты.'
             f'\n\n Подтвердить? ЗДЕСЬ КНОПКИ ПОДВЕРЖДЕНИЯ И ОТПРАВКА ЮЗЕРУ',
        reply_markup=await kbd.admin_payment_confirmation(params)
    )


@dp.callback_query(F.data.startswith('confirmed'))
async def confirmed_payment(callback_query):
    telegram_id = callback_query.from_user.id
    action = callback_query.data
    parts = action.split("_")
    subs = parts[1]
    user_id = parts[2]

    user_op = UsersOperations(DATABASE_URL)

    # создаем юзера в БД с подпиской, если такой юзер есть - функция только обновит/продлит подписку
    try:
        start = (await user_op.get_user_data(int(user_id))).get('subscription')
        start = datetime.fromtimestamp(start)
    except:
        start = datetime.now()


    if subs == '6 МЕСЯЦЕВ':
        period = start + relativedelta(months=6)
        subs = int(time.mktime(period.timetuple()))
    elif subs == '1 ГОД':
        period = start + relativedelta(years=1)
        subs = int(time.mktime(period.timetuple()))
    elif subs == 'НАВСЕГДА':
        period = start + relativedelta(years=100)
        subs = int(time.mktime(period.timetuple()))
    else:
        period = start + relativedelta(months=1)
        subs = int(time.mktime(period.timetuple()))

    #name = f'{callback_query.from_user.first_name} {callback_query.from_user.last_name}'
    params = {
        #'username':name,
        'telegram_id': int(user_id),
        'subscription': subs,
    }

    await user_op.upsert_user(params)

    params = await get_user_settings(int(user_id))
    #print(user_id)
    #print(params)

    #### telegram_id = message.from_user.id
    await bot.send_message(
        chat_id=user_id,
        text='ПОЗДРАВЛЯЕМ ОПЛАТА ПРОШЛА УСПЕШНО!',
        reply_markup = await kbd.main_menu(params)
    )

    await bot.send_message(
        chat_id=telegram_id,
        text=f'ПОДПИСКА ПОЛЬЗОВАТЕЛЯ УСПЕШНО ПОДВЕРЖДЕНА\n\n\n'
             f'user_id={user_id}\n'
             f'подписка = {subs}'
    )


@dp.message()
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(int(telegram_id))
    await bot.send_message(
        chat_id=telegram_id,
        text='Мы не можем распознать ваше сообщение, пожалуйста, воспользуйтесь кнопками меню'
             '\n⬇️⬇️⬇️',
        reply_markup=await kbd.main_menu(params)
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