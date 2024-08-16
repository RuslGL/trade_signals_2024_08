from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import os
from dotenv import load_dotenv


load_dotenv()

ADMIN_ID = os.getenv('owner_id')


# Класс для создания клавиатур
class Keyboards:

    def __init__(self):
        # Кнопка для возвращения в главное меню
        self.btn_back_to_main_menu = InlineKeyboardButton(
            text='⬅️В главное меню',
            callback_data='back_to_main_menu'
        )
        # Клавиатура с одной кнопкой для возвращения в главное меню
        self.single_btn_back_to_main_menu = InlineKeyboardMarkup(inline_keyboard=[
            [self.btn_back_to_main_menu],
        ])


#  ####### УПРАВЛЕНИЕ ПОДПИСКАМИ ########
#             ############
#               #####
    async def buy_subscription(self, params):

        btn_1 = InlineKeyboardButton(
            text='1 МЕСЯЦ',
            callback_data='one_month',
        )
        btn_2 = InlineKeyboardButton(
            text='6 МЕСЯЦЕВ',
            callback_data='six_month'
        )
        btn_3 = InlineKeyboardButton(
            text='1 ГОД',
            callback_data='one_year'
        )
        btn_4 = InlineKeyboardButton(
            text='НАВСЕГДА',
            callback_data='forewer'
        )

        btn_5 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )


        our_menu = [[btn_1, btn_2],
                    [btn_3, btn_4],
                    [btn_5]]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


    async def confirm_payment(self, params):
        user_id = params['id']
        subs = 'conf_' + params.get('subs')+'_'+str(user_id)
        # print(subs)
        btn_1 = InlineKeyboardButton(
            text='ОПЛАЧЕНО',
            callback_data=subs
        )

        our_menu = [[btn_1]]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


    async def admin_payment_confirmation(self, params):
        subs = params.get('subs')
        user_id = params.get('user_id')
        # print(params)
        call = 'confirmed_' + subs + '_' + str(user_id)
        # print(call)
        btn_1 = InlineKeyboardButton(
            text='ПОДТВЕРЖДАЮ',
            callback_data=call
        )

        our_menu = [[btn_1]]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


#  ####### ГЛАВНОЕ МЕНЮ ########
#             ############
#               #####

    async def main_menu(self, params):
        print(params)
        try:
            if params.get('stop_trading'):
                btn_trade = 'Включить торговлю'
            else:
                btn_trade = 'Выключить торговлю'
            if params.get('trade_type') == 'demo':
                btn_demo = 'Выкл демо-режим'
            else:
                btn_demo = 'Вкл демо-режим'
        except Exception as e:
            pass


        btn_1 = InlineKeyboardButton(
            text=btn_demo,
            callback_data='stop_demo',
        )
        btn_2 = InlineKeyboardButton(
            text='Запросить PNL',
            callback_data='menu_PNL'
        )
        btn_3 = InlineKeyboardButton(
            text=btn_trade,
            callback_data='stop_trade'
        )
        btn_4 = InlineKeyboardButton(
            text='Настройки торговли',
            callback_data='settings_menu'
        )

        btn_5 = InlineKeyboardButton(
            text='Управлять подпиской',
            callback_data='manage_subscription'
        )

        btn_6 = InlineKeyboardButton(
            text='Настройки торговли',
            callback_data='settings'
        )

        our_menu = [[btn_1, btn_2],
                    [btn_3, btn_4],
                    [btn_5],
                    [btn_6]]


        # Проверка на админские права и добавление кнопки
        if int(params.get('telegram_id')) == int(ADMIN_ID):
            btn_admin = InlineKeyboardButton(
                text='Админ меню',
                callback_data='admin_menu'
            )
            our_menu.append([btn_admin])

        return InlineKeyboardMarkup(inline_keyboard=our_menu)


#  ####### МЕНЮ АДМИНИСТРАТОРА ########
#             ############
#               #####

    async def admin_menu(self,):
        btn_1 = InlineKeyboardButton(
            text='Управлять каналами',
            callback_data='manage_chan',
        )
        btn_2 = InlineKeyboardButton(
            text='Управлять пользователями',
            callback_data='manage_users'
        )

        btn_3 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )

        our_menu = [[btn_1,],
                    [btn_2],
                    [btn_3]]

        return InlineKeyboardMarkup(inline_keyboard=our_menu)

# ####### УПРАВЛЕНИЕ КАНАЛАМИ (АДМИН) ########
#             ############
#               #####

    async def averaging_channels(self,):
        btn_1 = InlineKeyboardButton(
            text='Показать усредняющие каналы',
            callback_data='show_averaging',
        )
        btn_2 = InlineKeyboardButton(
            text='Добавить усредняющий канал',
            callback_data='add_averaging'
        )

        btn_3 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )

        our_menu = [[btn_1,],
                    [btn_2],
                    [btn_3]]

        return InlineKeyboardMarkup(inline_keyboard=our_menu)

# ####### УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (АДМИН) ########
#             ############
#               #####

    async def show_users(self,):
        btn_1 = InlineKeyboardButton(
            text='С ПОДПИСКОЙ',
            callback_data='users_active',
        )
        btn_2 = InlineKeyboardButton(
            text='БЕЗ ПОДПИСКИ',
            callback_data='users_inactive'
        )

        btn_3 = InlineKeyboardButton(
            text='Админ меню',
            callback_data='admin_menu'
        )

        our_menu = [[btn_1, btn_2],
                    [btn_3]]

        return InlineKeyboardMarkup(inline_keyboard=our_menu)


# ####### ВКЛ ВЫКЛ ТОРГОВЛИ (юзер) ########
#             ############
#               #####

# stop trade keyboard
    async def confirm_stop_trade_menu(self, params):
        if params.get('stop_trading'):
            text = 'Вкл торговлю'
        else:
            text = 'Выкл торговлю'

        btn_1 = InlineKeyboardButton(
            text=text,
            callback_data='stop_trade_confirmed',
        )
        btn_2 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )
        our_menu = [
            [btn_1, btn_2],
                    ]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


# ####### ВКЛ ВЫКЛ ДЕМО (юзер) ########
#             ############
#               #####
    # stop demo keyboard
    async def confirm_stop_demo_menu(self, params):
            if params.get('trade_type') == 'demo':
                text = 'Выкл демо-режим'
            else:
                text = 'Вкл демо-режим'

            btn_1 = InlineKeyboardButton(
                 text=text,
                 callback_data='stop_demo_confirmed',
            )
            btn_2 = InlineKeyboardButton(
                text='Главное меню',
                callback_data='main_menu'
            )
            our_menu = [
                [btn_1, btn_2],
            ]
            return InlineKeyboardMarkup(inline_keyboard=our_menu)


# ####### НАСТРОЙКИ ТОРГОВЛИ ########
#             ############
#               #####


