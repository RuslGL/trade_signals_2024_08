import time
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta



import os
import asyncio
from dotenv import load_dotenv



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
from code.db.pnl import PNLManager
from code.db.tg_channels import TgChannelsOperations

from code.api.account import find_usdt_budget, get_wallet_balance


load_dotenv()

kbd = Keyboards()

telegram_token = str(os.getenv('bot_token'))
channel_id = str(os.getenv('channel'))

DATABASE_URL = os.getenv('database_url')
db_users_op = UsersOperations(DATABASE_URL)


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


# ####### ПАРСИНГ ТОРГОВЫХ КАНАЛОВ ########
#            ############
#               #####

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


# Стартовая функция, отправляет сообщение администратору при запуске бота
async def on_startup():
    await bot.send_message(
        chat_id=ADMIN_ID,
        text='<b>Торговый бот был запущен!</b>',
        # reply_markup=kbd.single_btn_back_to_main_menu
        reply_markup=await kbd.admin_menu()
        )


@dp.callback_query(F.data == 'admin_menu')
async def start_admin_menu(callback_query):

    telegram_id = callback_query.from_user.id
    print(telegram_id )
    print(ADMIN_ID)
    params = await get_user_settings(telegram_id)
    # print(params)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return
    await bot.send_message(
        chat_id=telegram_id,
        text="🟢 Админ меню",
        reply_markup=await kbd.admin_menu()
    )


# ####### УПРАВЛЕНИЕ КАНАЛАМИ ########
#             ############
#               #####

@dp.callback_query(F.data == 'manage_chan')
async def manage_channels(callback_query):
    telegram_id = callback_query.from_user.id
    params = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return
    await bot.send_message(
        chat_id=telegram_id,
        text=(f"🟢 Для добавления каналов с базовыми сигналами просто добавьте телеграм бота в канал и предоставьте ему права администратора."
              f"\n\n⚡⚡ Дополнительных програмных настроек для считывания сигналов не требуется."
              f"\n\n🟢 В этом меню вы можете посмотреть список каналов для укрупнения/усреднения позиции и добавить такие каналы"),
        reply_markup=await kbd.averaging_channels()
    )


@dp.callback_query(F.data == 'add_averaging')
async def manage_channels(callback_query):
    telegram_id = callback_query.from_user.id
    params = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return
    await bot.send_message(
        chat_id=telegram_id,
        text="Для добавления нового канала отправьте его id в следующем формате: НОВЫЙ КАНАЛ -1234567789"
             "\n\n обратите внимание что id канала начинается со знака -",
    )


@dp.message(F.text.lower().startswith('новый канал'))
async def handle_new_channel_message(message: types.Message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(para)
        )
        return


    channel_id = str(message.text.split()[-1])

    try:
        await bot.send_message(
            chat_id=channel_id,
            text="Данный канал будет добавлен в список каналов для усреднения позиций",
        )
        ch_op = TgChannelsOperations(DATABASE_URL)
        await ch_op.upsert_channel({'telegram_id': str(channel_id)})

        telegram_id = message.from_user.id
        await bot.send_message(
            chat_id=telegram_id,
            text = '🟢 Добавление канала успешно завершено',
            reply_markup=await kbd.admin_menu()
        )
    except Exception as e:
        print(e)
        await bot.send_message(
            chat_id=telegram_id,
            text="Данный канал не может быть добавлен, возможные причины:"
                 "\n\n🔴канал уже в списке"
                 "\n\n🔴предоставленный id недействителен"
                 "\n\n🔴телеграм бот не добавлен в администраторы канала",
            reply_markup=await kbd.admin_menu()
        )

@dp.callback_query(F.data == 'show_averaging')
async def show_channels(callback_query):
    telegram_id = callback_query.from_user.id
    params = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return

    ch_op = TgChannelsOperations(DATABASE_URL)
    text = await ch_op.get_all_channels()

    text = '🟢 Список усредняющих каналов:\n\n' + ' \n\n'.join(text)
    print(text)

    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.admin_menu()
    )

    await bot.send_message(
        chat_id=telegram_id,
        text ="🔴 Для удаления канала отправьте его id в чат в следующем формате: УДАЛИТЬ КАНАЛ -1234567789"
              "\n\n обратите внимание что id канала начинается со знака -",
    )

@dp.message(F.text.lower().startswith('удалить канал'))
async def handle_delete_channel_message(message: types.Message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(para)
        )
        return

    channel_id = str(message.text.split()[-1])

    try:
        await bot.send_message(
            chat_id=channel_id,
            text="Данный канал будет удален из списка каналов для усреднения позиций",
        )
        ch_op = TgChannelsOperations(DATABASE_URL)
        await ch_op.delete_channel(channel_id)

        telegram_id = message.from_user.id
        await bot.send_message(
            chat_id=telegram_id,
            text='🟢 Удаление канала успешно завершено.'
                 '\n\n🔴 Не забудьте удалить бота из администраторов канала'
                 '\n\n иначе он продолжит считывать сигналы, как сигналы на покупку/продажу',
            reply_markup=await kbd.admin_menu()
        )
    except Exception as e:
        print(e)
        await bot.send_message(
            chat_id=telegram_id,
            text="Данный канал не может быть удален, возможные причины:"
                 "\n\n🔴канала нет в списке"
                 "\n\n🔴предоставленный id недействителен"
                 "\n\n🔴телеграм бот не добавлен в администраторы канала или удален из администраторов",
            reply_markup=await kbd.admin_menu()
        )

# ####### УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ADMIN) ########
#               ############
#                   #####

### 'manage_users'
@dp.callback_query(F.data == 'manage_users')
async def manage_users(callback_query):
    telegram_id = callback_query.from_user.id
    params = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(params)
        )
        return

    await bot.send_message(
        chat_id=telegram_id,
        text="🟢 Управление пользователями"
             "\n\nПоказать пользователей:",
        reply_markup=await kbd.show_users()
    )


@dp.callback_query(F.data.startswith('users_'))
async def show_users(callback_query):
    telegram_id = callback_query.from_user.id
    db_users = UsersOperations(DATABASE_URL)

    action = callback_query.data

    if  action == 'users_active':
        text_one = '🟢 Показать активных пользователей:'
        res = await db_users.get_active_users()
    else:
        text_one = '🛑 Показать пользователей без подписки:'
        res = await db_users.get_inactive_users()


    res = '\n\n'.join(
        f"{index + 1}. {item['username']} {item['telegram_id']}" for index, item in enumerate(res))

    text_two = ("🔴 Для удаления пользователя "
                "\n🔴 отправьте его id в чат"
                "\n🔴 в следующем формате:"
                "\n\nУДАЛИТЬ ПОЛЬЗОВАТЕЛЯ 1234567789")

    await bot.send_message(
        chat_id=telegram_id,
        text=f"{text_one}"
             f"\n\n{res}"
             f"\n\n{text_two}",
        reply_markup=await kbd.show_users()
    )

@dp.message(F.text.lower().startswith('удалить пользователя'))
async def handle_delete_user(message: types.Message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    if telegram_id != int(ADMIN_ID):
        await bot.send_message(
            chat_id=telegram_id,
            text="Вы не являетесь администратором",
            reply_markup=await kbd.main_menu(para)
        )
        return

    user_id = int(message.text.split()[-1])
    db_users = UsersOperations(DATABASE_URL)

    try:

        await db_users.delete_user(user_id)
        await bot.send_message(
            chat_id=telegram_id,
            text=f'🟢 Удаление пользователя {user_id} завершено.',
            reply_markup=await kbd.admin_menu()
        )
    except Exception as e:
        print(e)
        await bot.send_message(
            chat_id=telegram_id,
            text="⚡⚡⚡"
                 f"\n\nПользователь {user_id} не может быть удален, возможные причины:"
                 "\n\n🔴Данного пользователя нет в списке"
                 "\n\n🔴 Предоставленный id неверен (ошибка ввода)",
            reply_markup=await kbd.admin_menu()
        )

#########



# ####### USER INTERFACE ########
#     ############
#        #####



# ####### ВКЛ ВЫКЛ ТОРГОВЛИ (юзер) ########
#             ############
#               #####


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


@dp.callback_query(F.data == 'stop_trade_confirmed')
async def stop_trade_confirmed(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    status = para.get('stop_trading')
    # print(status)

    if not status:
        text = 'Торговля успешно отключена\n\n🟢 Управление торговлей'
        fields = {
            'stop_trading': True
        }
        # print('Otkluchaem torgovlu')

    else:
        text = ('🟢 Торговля успешно включена'
                '\n\n🔴 Не забудьте выключить демо-режим, если он включен'
                '\n\n🟢 Управление торговлей')
        fields = {
            'stop_trading': False
        }
        # print('Vkluchaem torgovlu')
    try:
        await db_users_op.update_user_fields(telegram_id, fields)
#### здесь выдаем параметры на подверждение
    except Exception as e:
        text = 'Сейчас невозможно изменить параметры, попробуйте позднее'

#### здесь выдаем параметры на подверждение
    para = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )


# ####### ВНЕСТИ API KEY SECRET KEY MAIN########
#             ############
#               #####

# main
@dp.message(F.text.lower().startswith('api key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    api_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    await user_op.update_user_fields(telegram_id, {'main_api_key': api_key})
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

# main
@dp.message(F.text.lower().startswith('secret key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)
    secret_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    await user_op.update_user_fields(telegram_id, {'main_secret_key': secret_key})


    ##### проверка работоспособности ключей через запрос баланса
    check = await get_wallet_balance(telegram_id)
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

    pnl_op = PNLManager(DATABASE_URL)
    await pnl_op.add_pnl_entry(
        {'user_id': telegram_id, 'total_budget': str(check)}
    )

    await bot.send_message(
        chat_id=telegram_id,
        text="SECRET KEY успешно получен и сохранен, теперь вы можете активировать режим торговли",
        reply_markup=await kbd.main_menu(params)
    )



# ####### ВКЛ ВЫКЛ ДЕМО (юзер) ########
#             ############
#               #####

@dp.callback_query(F.data == 'stop_demo')
async def stop_demo_confirmation(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(telegram_id)

    if params.get('trade_type') == 'demo':
        text = 'Вы уверены что хотите отключить демо-режим и начать Торговлю на реальном рынке?'
    else:
        text = 'Вы уверены что хотите включить демо-режим? '
        if not params.get('demo_secret_key') or not params.get('demo_api_key'):
            await bot.send_message(
                chat_id=telegram_id,
                text="🛑🛑🛑"
                     "\nОтсутствуют действующие API ключи для демо-торговли."
                     "\n\n🔐🔐🔐"
                     "\nОтправьте следующим сообщением Аpi key для демо-аккаунта"
                     "\n\n 📌📌📌"
                     "\n<b>Сообщение начните фразой \ndemo api key</b>,"
                     "\n"
                     "\n\nПРИМЕР:"
                     "\ndemo api key rtyvuA8WFFgjyuHv25"

            )
            return


    await bot.send_message(
        chat_id=telegram_id,
        text=text,

        reply_markup=await kbd.confirm_stop_demo_menu(params)
        )

@dp.message(F.text.lower().startswith('demo api key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    # params = await get_user_settings(telegram_id)
    api_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    await user_op.update_user_fields(telegram_id, {'demo_api_key': api_key})
    await bot.send_message(
        chat_id=telegram_id,
        text="API KEY для демо акканут успешно получен и сохранен"
             "\nОсталось отправить SECRET KEY"
             "\n\n🔐🔐🔐"
             "\nОтправьте следующим сообщением SECRET KEY для демо акканута"
             "\n\n 📌📌📌"
             "\n<b>Сообщение начните фразой \ndemo secret key</b>"
             "\n"
             "\n\nПРИМЕР:"
             "\ndemo secret key rtyvuA8WFFgjyuHv25rtyvuA8WFFgjyuHv25rtyvuA8WFFgjyuHv25"
    )

@dp.message(F.text.lower().startswith('demo secret key'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    secret_key = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    params = await get_user_settings(telegram_id)
    await user_op.update_user_fields(telegram_id, {'demo_secret_key': secret_key})


    ##### проверка работоспособности ключей через запрос баланса
    check = await get_wallet_balance(telegram_id, demo=True)
    if check == -1:
        print('invalid keys')
        await user_op.update_user_fields(telegram_id, {'demo_secret_key': None})
        await bot.send_message(
            chat_id=telegram_id,

            text="🔴Получены недействительные API ключи для демо аккаунта"
                 "\n\n🔴Проверьте, что вы отправили правильные данные, "
                 "\n\n🔴проверьте настройки ключей,"
                 "\n\n🔴при необходимости создайте новые ключи."
                 "\n\n🔐🔐🔐 После этого попробуйте отправить ключи заново",
            reply_markup=await kbd.main_menu(params)
        )
        return

    await user_op.update_user_fields(telegram_id, {'trade_type': 'demo'})
    params = await get_user_settings(telegram_id)
    await bot.send_message(
        chat_id=telegram_id,
        text="SECRET KEY успешно получен и сохранен, теперь вы можете активировать режим торговли",
        reply_markup=await kbd.main_menu(params)
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


# ####### ЗАПРОС PNL ########
#        ############
#          #####
@dp.callback_query(F.data == 'menu_PNL')
async def get_pnl(message):
    telegram_id = message.from_user.id
    para = await get_user_settings(telegram_id)
    pnl_op = PNLManager(DATABASE_URL)
    pnl = await pnl_op.calculate_percentage_difference(user_id=telegram_id)
    # print(pnl)
    default = ('💰 Недостаточно данных'
               '\n\n ⚡ Похоже вы недавно начали использование нашей торговой системы'
               '\n\n ⚡ Для минимального расчета торговый робот должен проработать больше суток')
    if not pnl:
        text = default
    else:
        text = (f'💰 PNL за период:'
                f'\n\n🟢 с начала торговли = {pnl.get("initial_vs_latest_percent", 0):.2f}%'
                f'\n💲  {pnl.get("initial_vs_latest", 0):.2f} USDT'
        
                f'\n\n🟢 за последний месяц = {pnl.get("month_ago_vs_latest_percent", 0):.2f}%'
                f'\n💲  {pnl.get("month_ago_vs_latest", 0):.2f} USDT'
        
                f'\n\n🟢 за прошедшую неделю = {pnl.get("week_ago_vs_latest_percent", 0):.2f}%'
                f'\n💲  {pnl.get("week_ago_vs_latest", 0):.2f} USDT'
        
                f'\n\n🟢 за прошедшие сутки = {pnl.get("day_ago_vs_latest_percent", 0):.2f}%'
                f'\n💲  {pnl.get("day_ago_vs_latest", 0):.2f} USDT'
        
                f'\n\n ⚡ расчет осуществляется по времени биржи, то есть UTC'
                f'\n\n ⚡⚡ для расчета принимаются закончившиеся сутки'
                f'\n\n ⚡⚡⚡ если вы вводили или выводили средства на торговый акканут, это искажает расчет.'
                f'\n\n ⚡⚡⚡ при ввыоде/выводе рекомендуем обнулить расчет и начать его с новго периода.')


    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.main_menu(para)
        )




#  ####### ГЛАВНОЕ МЕНЮ ########
#             ############
#               #####

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


#  ####### УПРАВЛЕНИЕ ПОДПИСКАМИ ########
#             ############
#               #####

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
             f'подписка = {subs}',
        reply_markup=await kbd.main_menu(params)

    )

# ####### НАСТРОЙКИ ТОРГОВЛИ ########
#             ############
#               #####
@dp.callback_query(F.data == 'settings')
async def settings(message: types.Message):
    telegram_id = message.from_user.id

    await bot.send_message(
        chat_id=telegram_id,
        text=(f'🔑  Вы перешли в режим настроек'
              f'\n\n🟢  Здесь можно изменить любую настройку и прочитать ее краткое описание'
              f'\n\n🔴  Внимание! '
              f'\nИзменяйте настройки, только если четко понимаете последствия своих действий и изменений'
              f'\n\n🔴🟢🔴'
              f'\n\nНастоятельно рекомендуем использовать отдельный аккаунт для работы настоящего робота,'
              f'\nесли вы будете дополнительно осуществлять торговлю на том же аккаунте или менять настройки'
              f'\nчерез web интерфейс это может повлечь сбои в работе торговго робота'),

        reply_markup=await kbd.show_settings()

    )

@dp.callback_query(F.data == 'open_settings')
async def open_settings(message: types.Message):
    telegram_id = message.from_user.id
    params = await get_user_settings(int(telegram_id))
    # print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=(f'🔐 Для получения описания или изменения настройки нажмите нужную кнопку'),
        reply_markup=await kbd.change_settings(params)

    )


@dp.callback_query(F.data.startswith('settings_'))
async def change_setting(callback_query):
    print('Мы в change_setting')
    telegram_id = callback_query.from_user.id
    db_users = UsersOperations(DATABASE_URL)
    params = await get_user_settings(int(telegram_id))
    #print(params)
    action = callback_query.data
    para = None
    text = 'необработанный вызов'

    if  action == 'settings_spot':
        setting = params.get(action[9:])
        para = action
        if setting:
            t = 'торговля на спотовом рынке'
        else:
            t = 'торговля фьючерсами'

        text = (f'🟢  Эта настройка определяет на каком рынке осуществляется торговля - на спотовом или фьючерсном'
                f'\n\n Текущая настройка {t}'
                f'\n\n При включении торговли фьючерсами будут изменены ваши торговые настройки на аккаунте биржи.'
                f'\nЭто может занять время до 20 секунд. Придется подождать'
                f'\n\n🔴  Хотите изменить?')


    if  action == 'settings_averaging':
        print(action)
        para = action
        setting = params.get(action[9:])
        if setting:
            t = '\n🟢 Сейчас усреднение включено'
        else:
            t = '\n🔴 Сейчас Усреднение выключено'

        text = (f'🟢  Эта настройка определяет будут ли укрупняться фьючерсные позиции и увеличиваться количеством монет на споте при получении сигнала на укрупнении'
                f'\n\n Текущая настройка {t}'
                f'\n\nХотите изменить?')


    if action == 'settings_isolated_margin':
        print(action)
        para = action
        setting = params.get(action[9:])
        if setting:
            t = '\n\n🟢 изолированная маржа'
        else:
            t = '\n\n🔴 кросс-маржа'

        text = (f'🟢 Тип маржи определяет, что происходит когда рынок идет против позиции и она подлежит ликвидации (особенно актуально при торговле с плечами)'
                f'\n\n🟢 При изолированной марже - риск ограничен суммой текущей позиции'
                f'\n\n🔴 При кросс марже - вы рискуете всем балансом'
                f'\n\n Текущая настройка: {t}'
                f'\n\nХотите изменить?')


    if  action == 'settings_min_trade':
        print(action)
        text = ('🟢 Начальный размер позиции определяет на какую сумму будут приобретаться монеты (спот) или открываться позиция (фьючерс).'
                '\n\nЕсли вы уже зарегистрировали api ключи (первично), то размер позиции был расчитан как 10% от вашего баланса.'
                '\n\nРеальный размер позиции может незначительно отличаться от текущей настройки, это вязано с проскальзываниями и настройками монет.'
                '\n\n🔑  Если вы хотите изменить настройку Минимальный размер'
                '\nотправьте следующим сообщением фразу'
                '\nМинимальный размер позиции и сумму в USDT, которую хотите установить как настройку'
                '\n\n🟢 ПРИМЕР:'
                '\nМинимальный размер 50'
                '\n\n🔴  учтите, что слишком маленький размер позиции, может не позволить вам купить часть активов\n\n'
                '(на каждую монету или фьючерс установлены ограничения по минимальной сумме торговли)'
    )

    if  action == 'settings_max_trade':
        print(action)
        text = ('🟢 Максимальный размер позиции определяет максимальную сумму, на которую могут приобретаться монеты (спот) или открываться позиция (фьючерс) с учетом укрупнений.'
                '\n\nЕсли вы уже зарегистрировали api ключи (первично), то размер позиции был расчитан как 100% от вашего баланса.'
                '\n\n🔑  Если вы хотите изменить настройку Максимальный размер позиции'
                '\nотправьте следующим сообщением фразу'
                '\nМаксимальный размер и сумму в USDT, которую хотите установить как настройку'
                '\n\n🟢 ПРИМЕР:'
                '\nМаксимальный размер 500')


    if  action == 'settings_averaging_size':
        print(action)
        text = ('🟢 Шаг укрупнения'
                '\n\nОпределяет насколько будет укрупняться позиция (кличество монет в торговле) при получении сигнала на укрупнение'
                '\n\n Доступные значения от 1.1 (на 10%) до 5 (на 500)'
                '\n\n🔑  Если вы хотите изменить настройку Шаг укрупнения'
                '\nотправьте следующим сообщением фразу'
                '\nШаг укрупнения и число, которое вы хотите установить'
                '\n\n🟢 ПРИМЕР:'
                '\nШаг укрупнения 1.5')

    if  action == 'settings_averaging_step':
        print(action)
        text = ('🟢 Условия укрупнения'
                '\n\nУкрупнение осуществляется только при условии, что цена сдвинулась против позиции (например, если открыт лонг - цена снижается)'
                '\n\n Настройка условия укрупнения определяет насколько в % должна измениться цена, чтобы состоялось укрупнение'
                '\n\n Если цена изменилась недостаточно, то укрупнение не осуществляется'
                '\n\n Доступные значения от 2% до 50%'
                '\n\n🔑  Если вы хотите изменить настройку Условия укрупнения'
                '\nотправьте следующим сообщением фразу'
                '\nУсловия укрупнения и число в процентах, которое вы хотите установить'
                '\n\n🟢 ПРИМЕР:'
                '\nУсловия укрупнения 7%')

    if  action == 'settings_tp_min':
        print(action)
        text = ('🟢 Условия открытия тейк-профита при движении цены в нужном направлении'
                '\n\nЦена должна измениться на указанный размер и только после этого выставляется ордер тейк-профит'
                '\n\n Доступные значения от 0.5% до 20%'
                '\n\n🔑  Если вы хотите изменить настройки открытия тейк профита'
                '\nотправьте следующим сообщением фразу'
                '\nТейк профит и число в процентах, которое вы хотите установить'
                '\n\n🟢 ПРИМЕР:'
                '\nТейк профит 2%')


    if  action == 'settings_tp_step':
        print(action)
        text = ('🟢 Торговый робот использует скользящий тейк профит, текущая настройка устанавливает на каком расстоянии за ценой двигается тейк профит'
                '\n\nЕсли цена продолжает двигаться в нужном направлении (например, продолжает расти при лонге), то тейк-профит продолжает двигаться за ценой на расстоянии, определенном текущей настройкой'
                '\n\n🔑  Если вы хотите изменить текущую настройку отправьте следующим сообщением слово'
                '\n\nСледуем и число от 0.1 до 2%.'
                '\n\n🟢 ПРИМЕР:'
                '\nСледуем 0.9%')


    if  action == 'settings_max_leverage':
        print(action)
        text = ('🟢 Размер плеча, используемый при торговле фьючерсами'
                '\n\n🔑  Если вы хотите изменить текущую настройку отправьте следующим сообщением фразу'
                '\n\nПлечо и целое число от 1 до 10, где 1 означает что плечо не применяется'
                '\n\n🟢 ПРИМЕР:'
                '\nПлечо 2'
                '\n\n🔴  Будьте разумны при установлении плечей, высокие плечи несут повышенные риски')

    if para:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=await kbd.confirm_settings_bool(para)

        )
    else:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            reply_markup=await kbd.show_settings()
        )


@dp.callback_query(F.data.startswith('yes_settings_'))
async def confirm_change(callback_query):
    print('Мы в confirm_change')
    telegram_id = callback_query.from_user.id
    db_users = UsersOperations(DATABASE_URL)
    params = await get_user_settings(int(telegram_id))
    print(params)
    action = callback_query.data[13:]
    text_1 = "🟢  Изменения применены!"
    text_2 = '🔴  Сейчас невозможно изменить параметры (возможно вы просто еще не отправили боту API ключи), попробуйте позднее'

    if action == 'spot':
        res =params.get(action)
        try:
            if res:
                ### сначала меняем плечи и маржу потом только в базу
                fields = {'spot': False}
                await db_users_op.update_user_fields(telegram_id, fields)
            else:
                fields = {'spot': True}
                await db_users_op.update_user_fields(telegram_id, fields)
            text = text_1 + "ИЗМЕНИТЬ ПЛЕЧИ И МАРЖУ ЧЕРЕЗ АПИ И НА ДЕМО И НА РЕАЛЬНОМ. ПРИ ПОДКЛЮЧЕНИИ ДЕМО АВТОМАТИЧЕСКИ ТОЖЕ ОБНОВИТЬ"
        except Exception as e:
            text = text_2


    if action == 'averaging':
        res = params.get(action)
        try:
            if res:
                fields = {'averaging': False}
                await db_users_op.update_user_fields(telegram_id, fields)
            else:
                fields = {'averaging': True}
                await db_users_op.update_user_fields(telegram_id, fields)
            text = text_1
        except Exception as e:
            text = text_2

    if action == 'isolated_margin':
        res = params.get(action)
        try:
            if res:
                fields = {'isolated_margin': False}
                await db_users_op.update_user_fields(telegram_id, fields)
            else:
                fields = {'isolated_margin': True}
                await db_users_op.update_user_fields(telegram_id, fields)
            text = text_1
        except Exception as e:
            text = text_2


    params = await get_user_settings(int(telegram_id))
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.change_settings(params)

    )

def convert_to_float(value):
    value = value.replace(' ', '').replace('%', '')
    value = value.replace(',', '.')
    float_value = float(value)
    return round(float_value, 1)

@dp.message(F.text.lower().startswith('минимальный размер'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        await user_op.update_user_fields(telegram_id, {'min_trade': result})
        text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )

@dp.message(F.text.lower().startswith('максимальный размер'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        await user_op.update_user_fields(telegram_id, {'max_trade': result})
        text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )

# Шаг укрупнения
@dp.message(F.text.lower().startswith('шаг укрупнения'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        if result < 1.1 or result > 5:
            text = ('🔴  Невозможно изменить параметры'
                    '\nДопустимые значения от 1.1 до 5')
        else:
            await user_op.update_user_fields(telegram_id, {'averaging_size': result})
            text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )

#условия укрупнения
@dp.message(F.text.lower().startswith('условия укрупнения'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        if result < 2 or result > 50:
            text = ('🔴  Невозможно изменить параметры'
                    '\nДопустимые значения от 2% до 50%')
        else:
            await user_op.update_user_fields(telegram_id, {'averaging_step': result})
            text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )

# Тейк профит
@dp.message(F.text.lower().startswith('тейк профит'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        if result < 0.5 or result > 20:
            text = ('🔴  Невозможно изменить параметры'
                    '\nДопустимые значения от 0.5% до 20%')
        else:
            await user_op.update_user_fields(telegram_id, {'tp_min': result})
            text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )



#Следуем и число от 0.1 до 2%.
#Следуем
@dp.message(F.text.lower().startswith('следуем'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        if result < 0.1 or result > 2:
            text = ('🔴  Невозможно изменить параметры'
                    '\nДопустимые значения от 0.1% до 2%')
        else:
            await user_op.update_user_fields(telegram_id, {'tp_step': result})
            text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )


#плечо от 1 до 10
@dp.message(F.text.lower().startswith('плечо'))
async def handle_api_key_message(message: types.Message):
    telegram_id = message.from_user.id
    result = str(message.text.split()[-1])
    user_op = UsersOperations(DATABASE_URL)
    try:
        result = convert_to_float(result)
        if not isinstance(result, int) and (result < 1 or result > 10):
            text = ('🔴  Невозможно изменить параметры'
                    '\nДопустимые значения целые числа от 0.1% до 2%')
        else:
            await user_op.update_user_fields(telegram_id, {'max_leverage': result})
            text = "🟢  Настройки успешно обновлены"
    except Exception as e:
        text = '🔴  Сейчас невозможно изменить параметры, попробуйте позднее'

    params = await get_user_settings(int(telegram_id))
    print(params)
    await bot.send_message(
        chat_id=telegram_id,
        text=text,
        reply_markup=await kbd.show_settings()
    )


#  ####### НЕИЗВЕСТНЫЕ СООБЩЕНИЯ ########
#             ############
#               #####
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









#  ####### ЗАПУСК БОТА ########
#             ############
#               #####

# async def start_bot():
#
#     await bot.delete_webhook(drop_pending_updates=True)
#     # dp.startup.register(on_startup)
#     try:
#         await dp.start_polling(bot)
#     finally:
#         await bot.session.close()

async def start_bot():
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot, polling_timeout=1)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(start_bot())