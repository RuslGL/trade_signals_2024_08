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
            text=f'1 МЕСЯЦ {params.get('1 МЕСЯЦ').get('cost')} 💰',
            callback_data='one_month',
        )
        btn_2 = InlineKeyboardButton(
            text=f'6 МЕСЯЦЕВ {params.get('6 МЕСЯЦЕВ').get('cost')} 💰',
            callback_data='six_month'
        )
        btn_3 = InlineKeyboardButton(
            text=f'1 ГОД {params.get('1 ГОД').get('cost')} 💰',
            callback_data='one_year'
        )
        btn_4 = InlineKeyboardButton(
            text=f'НАВСЕГДА {params.get('НАВСЕГДА').get('cost')} 💰',
            callback_data='forewer'
        )

        btn_5 = InlineKeyboardButton(
            text='📛 Главное меню 📛',
            callback_data='main_menu'
        )


        our_menu = [[btn_1, btn_2],
                    [btn_3, btn_4],
                    [btn_5]]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


    async def confirm_payment(self, params):
        user_id = params['id']
        subs = 'conf_' + params.get('subs')+'_'+str(user_id)
        btn_1 = InlineKeyboardButton(
            text='ОПЛАЧЕНО',
            callback_data=subs
        )

        our_menu = [[btn_1]]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


    async def admin_payment_confirmation(self, params):
        subs = params.get('subs')
        user_id = params.get('user_id')
        call = 'confirmed_' + subs + '_' + str(user_id)
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
            text=f'✅ {btn_demo} ✅',
            callback_data='stop_demo',
        )
        btn_2 = InlineKeyboardButton(
            text='🤑 Запросить PNL 🤑',
            callback_data='menu_PNL'
        )
        btn_3 = InlineKeyboardButton(
            text=f'💰 {btn_trade} 💰',
            callback_data='stop_trade'
        )
        btn_4 = InlineKeyboardButton(
            text='⚙️ Настройки торговли ⚙️',
            callback_data='settings'
        )

        btn_5 = InlineKeyboardButton(
            text='🔑 Обновить API ключи 🔑',
            callback_data='change_api'
        )

        btn_6 = InlineKeyboardButton(
            text='🚧 Управлять подпиской 🚧',
            callback_data='manage_subscription'
        )

        btn_7 = InlineKeyboardButton(
            text='⛔️ ЗАКРЫТЬ ВСЕ ПОЗИЦИИ ⛔️',
            callback_data='stop_all'
        )


        our_menu = [[btn_1, btn_2],
                    [btn_3, btn_4],
                    [btn_5, btn_6],
                    [btn_7],]


        # Проверка на админские права и добавление кнопки
        if int(params.get('telegram_id')) == int(ADMIN_ID):
            btn_admin = InlineKeyboardButton(
                text='🚨 Админка 🚨',
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

# ####### ОБНУЛИТЬ РАСЧЕТ PNL (юзер) ########
#             ############
#               #####

    async def clean_pnl(self,):
            btn_1 = InlineKeyboardButton(
                 text="Обнулить расчет PNL",
                 callback_data='clean_pnl',
            )
            btn_2 = InlineKeyboardButton(
                text='Главное меню',
                callback_data='main_menu'
            )
            our_menu = [
                [btn_1,],
                [btn_2],
            ]
            return InlineKeyboardMarkup(inline_keyboard=our_menu)

# ####### ЗАКРЫТЬ ВСЕ ПОЗИЦИИ (юзер) ########
#             ############
#               #####


    async def confirm_stop(self, params):
        btn_1 = InlineKeyboardButton(
            text="Закрыть всё",
            callback_data='confirm_stop',
        )
        btn_2 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )
        our_menu = [
            [btn_1, ],
            [btn_2],
        ]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)

# ####### НАСТРОЙКИ ТОРГОВЛИ ########
#             ############
#               #####

    async def show_settings(self):
            btn_1 = InlineKeyboardButton(
                 text= 'Открыть настройки',
                 callback_data='open_settings',
            )
            btn_2 = InlineKeyboardButton(
                text='Главное меню',
                callback_data='main_menu'
            )
            our_menu = [
                [btn_1],
                [btn_2],
            ]
            return InlineKeyboardMarkup(inline_keyboard=our_menu)

    async def change_settings(self, params):
            if params.get('spot') == True:
                text = 'Тип торговли - спотовая'
            else:
                text = 'Тип торговли - фьючерсы'

            btn_1 = InlineKeyboardButton(
                 text= text,
                 callback_data='settings_spot',
            )

            btn_2 = InlineKeyboardButton(
                 text= f'Начальный размер позиции {params.get('min_trade')} USDT',
                 callback_data='settings_min_trade',
            )

            btn_3 = InlineKeyboardButton(
                 text= f'Максимальный размер позиции {params.get('max_trade')} USDT',
                 callback_data='settings_max_trade',
            )

            if params.get('averaging') == True:
                text = 'Применяется усреднение позиции'
            else:
                text = 'Усреднение позиции не применяется'

            btn_4 = InlineKeyboardButton(
                text=text,
                callback_data='settings_averaging',
            )

            btn_5 = InlineKeyboardButton(
                 text= f'Множитель объема ордеров {params.get('averaging_size')}',
                 callback_data='settings_averaging_size',
            )

            item = params.get('averaging_step')
            if item == 0.01:
                item = 0

            btn_6 = InlineKeyboardButton(
                 text= f'Отклонение цены {item}%',
                 callback_data='settings_averaging_step',
            )

            btn_7 = InlineKeyboardButton(
                 text= f'Take Profit {params.get('tp_min')}%',
                 callback_data='settings_tp_min',
            )

            btn_8 = InlineKeyboardButton(
                 text= f'Trailing отклонение {params.get('tp_step')}%',
                 callback_data='settings_tp_step',
            )

            btn_9 = InlineKeyboardButton(
                 text= f'Максимальное плечо (фьючерсы) {params.get('max_leverage')}',
                 callback_data='settings_max_leverage',
            )

            btn_10 = InlineKeyboardButton(
                text='Trailing Buy',
                callback_data='settings_trade_pair_if'
            )


            btn_11 = InlineKeyboardButton(
                text='Торгуемые монеты',
                callback_data='coins'
            )

            btn_12 = InlineKeyboardButton(
                text='Меню настроек',
                callback_data='settings'
            )


            our_menu = [[btn_1], [btn_2], [btn_3],[btn_4],
                        [btn_5], [btn_6], [btn_7], [btn_8],
                        [btn_9], [btn_10], [btn_11], [btn_12]]
            return InlineKeyboardMarkup(inline_keyboard=our_menu)



    async def coins_settings(self, params):
        tr_p = params.get('trading_pairs')
        if "-1" in tr_p:
            text_1 = "✅ Торг. новыми монетами. Выключить?"
        else:
            text_1 = "⛔️ Торг. новыми монетами. Включить?"

        btn_1 = InlineKeyboardButton(
             text= text_1,
             callback_data='new_coins_on_off',
        )
        if "-1" not in tr_p and tr_p:
            text_2 = '✅ Выбран список торгуемых монет'
        else:
            text_2 = '⛔️ Список торгю монет не выбран'
        btn_2 = InlineKeyboardButton(
             text=text_2,
             callback_data='chose_coins',
        )

        if not tr_p:
            text_3 = '✅ Включена торговля всеми монетами'
        else:
            text_3 = '⛔️ Торговля всеми монетами не выбрана'
        btn_3 = InlineKeyboardButton(
             text=text_3,
             callback_data='all_coins',
        )


        btn_4 = InlineKeyboardButton(
             text= 'Открыть настройки',
             callback_data='open_settings',
        )
        btn_5 = InlineKeyboardButton(
            text='Главное меню',
            callback_data='main_menu'
        )
        our_menu = [
            [btn_1],
            [btn_2],
            [btn_3],
            [btn_4],
            [btn_5],
        ]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)


    async def change_coins(self, params):

        btn_1 = InlineKeyboardButton(
             text= "Добавить монеты в список",
             callback_data='add_coins',
        )

        btn_2 = InlineKeyboardButton(
             text= 'Открыть настройки',
             callback_data='open_settings',
        )

        btn_3 = InlineKeyboardButton(
             text='Вернуться в главное меню',
             callback_data='main_menu',
        )


        our_menu = [
            [btn_1],
            [btn_2],
            [btn_3],
        ]
        return InlineKeyboardMarkup(inline_keyboard=our_menu)

    async def confirm_settings_bool(self, params):
            btn_1 = InlineKeyboardButton(
                 text= 'Да',
                 callback_data=f'yes_{params}',
            )

            btn_2 = InlineKeyboardButton(
                 text= 'Нет',
                 callback_data='open_settings',
            )


            btn_3 = InlineKeyboardButton(
                 text= 'Открыть настройки',
                 callback_data='open_settings',
            )
            btn_4 = InlineKeyboardButton(
                text='Главное меню',
                callback_data='main_menu'
            )
            our_menu = [
                [btn_1],
                [btn_2],
                [btn_3],
                [btn_4],
            ]
            return InlineKeyboardMarkup(inline_keyboard=our_menu)