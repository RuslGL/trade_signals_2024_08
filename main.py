import asyncio
import os
import time

from datetime import datetime, timedelta

from warnings import filterwarnings
filterwarnings("ignore")

from datetime import datetime, timedelta, timezone

from multiprocessing import Process, Queue
from dotenv import load_dotenv

import traceback
import uuid




from db.pairs import SpotPairsOperations, LinearPairsOperations
from db.users import UsersOperations
from db.tg_channels import TgChannelsOperations
from db.signals import SignalsOperations
from db.pnl import PNLManager
from db.positions import PositionsOperations

from api.market import process_spot_linear_settings, get_prices
from api.account import get_wallet_balance, find_usdt_budget, get_user_orders
from api.utils import calculate_purchase_volume, round_price, adjust_quantity
from api.trade import (universal_spot_conditional_market_order, unuversal_linear_conditional_market_order,
                       amend_spot_conditional_market_order, universal_market_order, set_tp_linears)


from tg.main_func import start_bot
import code.settings as st

import warnings

# Отключение всех предупреждений
warnings.filterwarnings("ignore")

load_dotenv()

DATABASE_URL = str(os.getenv('database_url'))

trade_url = st.base_url
demo_url = st.demo_url

order_trade_url = trade_url + st.ENDPOINTS.get('place_order')
order_demo_url = demo_url + st.ENDPOINTS.get('place_order')

user_orders_trade_url = trade_url + st.ENDPOINTS.get('get_orders')
user_orders_demo_url = demo_url + st.ENDPOINTS.get('get_orders')

amend_order_trade_url = trade_url + st.ENDPOINTS.get('amend_order')
amend_order_demo_url = demo_url + st.ENDPOINTS.get('amend_order')

# Create a global queue to store the price data
price_queue = Queue()


async def on_start(db_spot_pairs, db_linear_pairs, db_users, db_tg_channels, db_signals, db_positions):
    # Асинхронно создаем таблицы и получаем все торгуемые пары спот и фьюч с их настройками
    tasks = [
        asyncio.create_task(process_spot_linear_settings()),
        asyncio.create_task(db_spot_pairs.create_table()),
        asyncio.create_task(db_linear_pairs.create_table()),
        asyncio.create_task(db_users.create_table()),
        asyncio.create_task(db_tg_channels.create_table()),
        asyncio.create_task(db_signals.create_table()),
        asyncio.create_task(db_positions.create_table()),
    ]

    tasks_res = await asyncio.gather(*tasks)

    # Вносим в базу данных все настройки
    # Периодически обновлять
    tasks = [
        asyncio.create_task(db_spot_pairs.insert_spot_pairs(tasks_res[0][0])),
        asyncio.create_task(db_linear_pairs.insert_linear_pairs(tasks_res[0][1])),
    ]
    await asyncio.gather(*tasks)
    await start_bot()

async def trade_performance(database_url, price_queue):
    signals_op = SignalsOperations(database_url)
    db_tg_channels = TgChannelsOperations(database_url)
    users_op = UsersOperations(database_url)
    spot_set_op = SpotPairsOperations(database_url)
    lin_set_op = LinearPairsOperations(database_url)
    positions_op = PositionsOperations(database_url)


    while True:
        try:
            # ####### SIGNAL LOGIC STARTS HERE ########
            #               ############
            #                   #####

            signal = await signals_op.get_and_clear_all_signals()
            users = await users_op.get_all_users_data()
            # users = await users_op.get_all_users_data()

            # get users settings coin settings etc



            if signal:
                coin = signal[next(iter(signal))]['coin']
                signal_details = (signal[next(iter(signal))]['direction'],
                                  coin,
                                  signal[next(iter(signal))]['channel_id'])

                print('New signal received', signal_details)

                #################### GATHER REQUESTS #######################
                averaging_channels = await db_tg_channels.get_all_channels()
                spot_data = await spot_set_op.get_all_spot_pairs_data()
                linear_data = await lin_set_op.get_all_linear_pairs_data()

                # get USERS SETTINGS



                # print(averaging_channels)
                if signal_details[2] in averaging_channels:
                    averaging = True  # averaging trade logic
                    print('Signal type - averaging')
                else:
                    averaging = False  # main trade logic
                    print('Signal type - ordinary')

                spot_prices, linear_prices = price_queue.get()


                # Получаем доступные бюджеты для всех пользователей (real и demo)
                tasks_budget = []
                user_task_map = {}

                for index, row in users.iterrows():
                    user_id = row['telegram_id']

                    if row['trade_type'] == 'demo':
                        # url = demo_url + st.ENDPOINTS.get('wallet-balance')
                        task = asyncio.create_task(find_usdt_budget(user_id, demo=True))
                    else:
                        # url = trade_url + st.ENDPOINTS.get('wallet-balance')
                        task = asyncio.create_task(find_usdt_budget(user_id, demo=False))

                    tasks_budget.append(task)
                    user_task_map[task] = user_id

                budget_results = await asyncio.gather(*tasks_budget)
                budget_map = {user_task_map[task]: result for task, result in zip(tasks_budget, budget_results)}
                symbol = coin.upper() + 'USDT'
                # print('coin.upper() - на уровне сигнала', coin.upper())
                # print('symbol - на уровне сигнала', symbol)
                # print('budget_map - на уровне сигнала', budget_map)

            #               #####
            #           ############
            # ####### SIGNAL LOGIC ENDS HERE ########

                # ####### START MAIN TRADE LOGIC ########
                #              ############
                #                 #####

                # проверять список монет, проверять подписку

                if not averaging:
                    print('Start main trade logic')

                    # Разделяем пользователей на спотовых и линейных
                    users_spot = users[users['spot'] == True]
                    users_linear = users[users['spot'] != True]

                    tasks = []

                    # по торговой стратегии у спота могут быть только лонги
                    spot_price = spot_prices.get(symbol)

                    if signal_details[0] == 'buy' and spot_price:
                        print('Start spot long', symbol, spot_price)

                        # Получаем спотовые торговые настройки для символа
                        spot_settings = spot_data.get(coin.upper())
                        spot_min_volume = spot_settings.get('min_order_qty')
                        spot_qty_tick = spot_settings.get('base_precision')
                        spot_price_tick = spot_settings.get('tick_size')

                        for_spot_orders = {}
                        # Создаем заказы для пользователей
                        for user_id in users_spot['telegram_id']:
                            user = users[users['telegram_id'] == user_id]
                            #print('user in spot buy', user)

                            # На уровне канала и спот бай проверяем настройки и подписку юзера
                            if int(time.time()) > user['subscription'].iloc[0]:
                                print('Подписка истекла - алерт юзеру')
                                continue
                            if user['stop_trading'].iloc[0]:
                                continue
                            # пока нет проверки на new pairs надо ее проверить на стадии получения сигнала
                            if user['trading_pairs'].iloc[0] and symbol not in user['trading_pairs'].iloc[
                                0] and '-1' not in user['trading_pairs'].iloc[0]:
                                print('not in trading pairs')
                                continue

                            # считаем на какой процент (1.001/1.01) и т.п. нужно увеличить цену чтобы лонговать, настройка trade_pair_if
                            trade_pair_if_buy = float(users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1
                            # допускаемое проскальзывание
                            trade_pair_if_slip_buy = float(
                                users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1.002

                            # рассчитываем сумму позиции как наименьшее доступный бюджет USDT и настройка min_trade
                            sum_amount = min(float(users[users['telegram_id'] == user_id]['min_trade']),
                                             float(budget_map[user_id]))
                            # рассчитываем кастомной функцией тригерную цену для conditional spot order и цену с учетом проскальзывания
                            trigger_price = round_price(float(spot_price) * trade_pair_if_buy, float(spot_price_tick))
                            price = round_price(float(spot_price) * trade_pair_if_slip_buy, float(spot_price_tick))

                            # Рассчитываем количнство монеты к покупке с учетом сеттингов монеты
                            qty_info_spot = calculate_purchase_volume(sum_amount, spot_price, spot_min_volume,
                                                                      spot_qty_tick)

                            print('Покупка для спот лонга', users[users['telegram_id'] == user_id]['username'], sum_amount, trigger_price, qty_info_spot)
                            # если функция возвращает отриц значение значит сумма недостаточ - пропуск для этого юзера
                            if qty_info_spot < 0:
                                continue

                            # Сохраняем данные для ордеров
                            for_spot_orders[user_id] = {
                                'sum_amount': sum_amount,
                                'qty_info': qty_info_spot,
                                'price': price,
                                'triggerPrice': trigger_price,

                            }

                        # Формируем и отправляем ордера
                        # tasks = []
                        for user_id, order_data in for_spot_orders.items():
                            user_info = users_spot[users_spot['telegram_id'] == user_id].iloc[0]

                            # Определяем URL и ключи в зависимости от типа аккаунта
                            api_url = order_demo_url if user_info['trade_type'] == 'demo' else order_trade_url
                            api_key = user_info['demo_api_key'] if user_info['trade_type'] == 'demo' else \
                                user_info['main_api_key']
                            secret_key = user_info['demo_secret_key'] if user_info['trade_type'] == 'demo' else \
                                user_info['main_secret_key']
                            orderLinkId = f'{user_id}_demo_spot_{uuid.uuid4().hex[:12]}' if user_info[
                                                                                                'trade_type'] == 'demo' else \
                                f'{user_id}_real_spot_{uuid.uuid4().hex[:12]}'
                            print('Задача на ордер', api_url, api_key, secret_key, symbol, 'Buy', order_data['qty_info'],
                                  order_data['price'], order_data['triggerPrice'], orderLinkId)
                            # Создаем задачу для выполнения ордера
                            task = asyncio.create_task(
                                universal_spot_conditional_market_order(
                                    api_url, api_key, secret_key, symbol, 'Buy',
                                    order_data['qty_info'], order_data['price'], order_data['triggerPrice'],
                                    orderLinkId
                                )
                            )
                            tasks.append(task)


                    ###### linears
                    # по торговой стратегии у фьючей могут быть и лонги и шорты
                    linear_price = linear_prices.get(coin.upper() + 'USDT', None)
                    if linear_price:
                        print('Start linear long', linear_price)

                        # Получаем фьючерсные торговые настройки для символа
                        linear_settings = linear_data.get(coin.upper())

                        linear_min_volume = linear_settings.get('min_order_qty')
                        linear_qty_tick = linear_settings.get('qty_step')
                        linear_price_tick = linear_settings.get('price_tick_size')
                        # print(linear_min_volume, linear_qty_tick, linear_price_tick)

                        for_linear_orders = {}

                        for user_id in users_linear['telegram_id']:
                            user_set = users[users['telegram_id'] == user_id].iloc[0]

                            # На уровне канала и линеар лонг/шорт проверяем настройки и подписку юзера
                            if int(time.time()) > user_set['subscription']:
                                print('Подписка истекла - алерт юзеру')
                                continue
                            if user_set['stop_trading']:
                                continue
                            # пока нет проверки на new pairs надо ее проверить на стадии получения сигнала
                            if user_set['trading_pairs'] and symbol not in user_set[
                                'trading_pairs'] and '-1' not in user_set['trading_pairs']:
                                print('not in trading pairs')
                                continue
                            # 1692124800

                            if signal_details[0] == 'buy':
                                # считаем на какой процент (1.001/1.01) и т.п. нужно увеличить цену чтобы лонговать, настройка trade_pair_if
                                tp_min_buy = float(users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1
                                side = 'Buy'
                                triggerDirection = 1

                            if signal_details[0] == 'sell':
                                print('Продаем')
                                # считаем на какой процент (99.9/99.99) и т.п. нужно уменьшить цену чтобы шортить, настройка trade_pair_if
                                tp_min_buy = abs(float(user_set['trade_pair_if']) / 100 - 1)
                                side = 'Sell'
                                triggerDirection = 2

                            # рассчитываем сумму позиции как наименьшее доступный бюджет USDT и настройка min_trade
                            # ВНИМАНИЕ! Плечо в расчет не берется, оно позволяет только открыть больше позиций
                            sum_amount = min(float(user_set['min_trade']), float(budget_map[user_id]))

                            # рассчитываем кастомной функцией тригерную цену для conditional linear order
                            # tp_min_buy уже учитывает в какую сторону должна двигаться цена
                            trigger_price_value = round_price(float(linear_price) * tp_min_buy,
                                                              float(linear_price_tick))

                            # Рассчитываем количество монеты к покупке с учетом сеттингов монеты
                            qty_info = calculate_purchase_volume(sum_amount, trigger_price_value, linear_min_volume,
                                                                 linear_qty_tick)

                            # если функция возвращает отриц значение значит сумма недостаточ - пропуск для этого юзера
                            if qty_info < 0:
                                continue
                            # Сохраняем данные для ордеров
                            for_linear_orders[user_id] = {
                                'sum_amount': sum_amount,
                                'triggerPrice': trigger_price_value,
                                # 'price': price_value,
                                'qty_info': qty_info
                            }

                        # Формируем и отправляем ордера
                        # tasks = []


                        for user_id, order_data in for_linear_orders.items():
                            user_info = users_linear[users_linear['telegram_id'] == user_id].iloc[0]

                            # Определяем URL и ключи в зависимости от типа аккаунта
                            api_url = order_demo_url if user_info['trade_type'] == 'demo' else order_trade_url
                            api_key = user_info['demo_api_key'] if user_info['trade_type'] == 'demo' else user_info[
                                'main_api_key']
                            secret_key = user_info['demo_secret_key'] if user_info['trade_type'] == 'demo' else \
                                user_info['main_secret_key']

                            orderLinkId = f'{user_id}_demo_linear_{uuid.uuid4().hex[:12]}' if user_info[
                                                                                                  'trade_type'] == 'demo' else \
                                f'{user_id}_real_linear_{uuid.uuid4().hex[:12]}'

                            # Создаем задачу для выполнения фьючерсного ордера
                            task = asyncio.create_task(
                                unuversal_linear_conditional_market_order(
                                    api_url, api_key, secret_key, symbol, side,
                                    order_data['qty_info'], order_data['triggerPrice'],
                                    triggerDirection, orderLinkId
                                )
                            )
                            tasks.append(task)

                    # Выполняем все задачи спот/линеар лонг/шорт параллельно и собираем результаты
                    results = await asyncio.gather(*tasks)
                    # print(results)
                    if signal_details[0] == 'buy':
                        side = 'Buy'
                    else:
                        side = 'Sell'



                    # пробуем ассинхронно отправить в БД

                    tasks = []

                    for position in results:
                        if isinstance(position, dict) and position.get('retMsg') == 'OK':
                            res = position.get('result')
                            print(res)
                            orderLinkId = res.get('orderLinkId')
                            details = orderLinkId.split('_')

                            pos = {
                                "bybit_id": orderLinkId,
                                "owner_id": int(details[0]),
                                "market": details[1],
                                "order_type": details[2],
                                "symbol": symbol,
                                "side": side,
                            }

                            # Создаем задачу для вставки позиции с обработкой ошибок
                            tasks.append(
                                asyncio.create_task(
                                    positions_op.upsert_position(pos)
                                )
                            )

                    # Выполняем все задачи параллельно
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # Обработка результатов выполнения задач
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                            print(f"Ошибка при вставке позиции {tasks[i].get_name()}: {result}")
                            try:
                                # Повторная попытка вставки
                                await positions_op.upsert_position(tasks[i].get_name())
                            except Exception as e:
                                print(f"Повторная попытка не удалась для позиции {tasks[i].get_name()}: {e}")


                    # сохраняем исполненные в positions выше пробуем тоже но ассинхронно
                    # for position in results:
                    #     if isinstance(position, dict) and position.get('retMsg') == 'OK':
                    #         res = position.get('result')
                    #         print(res)
                    #         orderLinkId = res.get('orderLinkId')
                    #         details = orderLinkId.split('_')
                    #
                    #         pos = {
                    #             "bybit_id": orderLinkId,
                    #             "owner_id": int(details[0]),
                    #             "market": details[1],
                    #             "order_type": details[2],
                    #             "symbol": symbol,
                    #             "side": side,
                    #         }
                    #         await positions_op.upsert_position(pos)

                #####################################################

                #                    #####
                #                ############
                # ####### STOP MAIN TRADE LOGIC ########


                # ####### START AVERAGING TRADE LOGIC ########
                #               ############
                #                   #####
                if averaging:
                    print('Start averaging logic')
                    symbol = coin.upper() + 'USDT'
                    # получаем открытые (выкупленные) позиции у которых еще не тригернулся ТП и у которых совпадает символ
                    try:
                        closed_positions_no_tp = (await positions_op.get_positions_by_fields(
                            {'orderStatus': True, 'tp_opened': False, 'depends_on': '-1', 'symbol': symbol
                             }))

                        if closed_positions_no_tp.empty:
                            print('Нет открытых позиций для укрупнения')
                            continue

                        if signal_details[0] == 'buy':
                            side = 'Buy'
                        else:
                            side = 'Sell'

                        spot_price = spot_prices.get(symbol)
                        linear_price = linear_prices.get(symbol)

                        # чась символов может быть только в споте или только фьючах
                        try:
                            spot_settings = spot_data.get(coin.upper())
                            spot_min_volume = spot_settings.get('min_order_qty')
                            spot_qty_tick = spot_settings.get('base_precision')
                        except:
                            pass

                        try:
                            linear_settings = linear_data.get(coin.upper())
                            linear_min_volume = linear_settings.get('min_order_qty')
                            linear_qty_tick = linear_settings.get('qty_step')
                        except:
                            pass

                        closed_positions_no_tp = closed_positions_no_tp[['owner_id', 'symbol', 'side',
                                                                         'bybit_id', 'avgPrice', 'cumExecValue',
                                                                         'order_type', 'cumExecQty', 'market']]


                        print('Проверяем условия усреднения')


                        # ОБЕРНУТЬ В ТРАЙ ЭКСЕПТ
                        for index, row in closed_positions_no_tp.iterrows():
                            user = users[users['telegram_id'] == row['owner_id']]
                            # если включен стоп трейд пропускаем юзера
                            if user['stop_trading'].iloc[0]:
                                continue
                            averaging = user['averaging'].iloc[0]
                            max_trade = float(user['max_trade'].iloc[0])
                            if averaging:
                                averaging_step = float(user['averaging_step'].iloc[0])
                                averaging_size = float(user['averaging_size'].iloc[0])
                                prev_price = float(row['avgPrice'])
                                prev_volume = float(row['cumExecQty'])
                                extra_volume = abs((prev_volume * averaging_size) - prev_volume)

                                spot_price = spot_prices.get(symbol)
                                linear_price = linear_prices.get(symbol)


                                if row['order_type'] == 'spot':
                                    category = 'spot'
                                    print(row['order_type'])
                                    current_price = float(spot_price)
                                    limit_volume = max_trade / current_price
                                    if extra_volume + prev_volume >= limit_volume:
                                        extra_volume = limit_volume - prev_volume
                                    limit_budget = float(budget_map[row['owner_id']]) / current_price
                                    if extra_volume > limit_budget:
                                        extra_volume = limit_budget

                                    extra_volume = adjust_quantity(extra_volume, spot_min_volume, spot_qty_tick)
                                    print(extra_volume, 'extra_volume')
                                else:
                                    current_price = float(linear_price)
                                    limit_volume = max_trade / current_price
                                    if extra_volume + prev_volume >= limit_volume:
                                        extra_volume = limit_volume - prev_volume
                                    limit_budget = float(budget_map[row['owner_id']]) / current_price
                                    if extra_volume > limit_budget:
                                        extra_volume = limit_budget

                                    category = 'linear'
                                    extra_volume = adjust_quantity(extra_volume, linear_min_volume, linear_qty_tick)
                                    print(extra_volume, 'extra_volume')

                                if extra_volume == -1:
                                    print('Недостаточно объема для минимальной покупки усреднения')


                                if side == 'Buy':
                                    if prev_price < current_price:
                                        print('No averaging for buy')
                                    else:
                                        print('lets check averaging details for buy')
                                        per_cent = abs(current_price - prev_price) / prev_price * 100
                                        if per_cent >= averaging_step:
                                            print(f'lets buy extra {extra_volume}')
                                            trade_type = user['trade_type'].iloc[0]
                                            print(trade_type)
                                            if trade_type == 'demo':
                                                api_url = order_demo_url
                                                api_key = user['demo_api_key'].iloc[0]
                                                print('api_key', api_key)
                                                secret_key = user['demo_secret_key'].iloc[0]
                                                print('secret_key', secret_key)
                                                orderLinkId = f"{str(row['owner_id'])}_demo_aver_{uuid.uuid4().hex[:8]}"
                                                # print('orderLinkId', orderLinkId)
                                            else:
                                                api_url = order_trade_url
                                                api_key = user['main_api_key'].iloc[0]
                                                print('api_key', api_key)
                                                secret_key = user['main_secret_key'].iloc[0]
                                                print('api_key', api_key)
                                                orderLinkId = f"{str(row['owner_id'])}_real_aver_{uuid.uuid4().hex[:8]}"

                                            res = await universal_market_order(api_url, str(api_key), str(secret_key), category, symbol,
                                                                          side, extra_volume, orderLinkId)
                                            print(res)

                                            if isinstance(res, dict) and res.get('retMsg') == 'OK':
                                                result = res.get('result')
                                                orderLinkId = result.get('orderLinkId')
                                                depends = row['bybit_id']
                                                pos = {
                                                    "bybit_id": orderLinkId,
                                                    "owner_id": int(row['owner_id']),
                                                    "market": user['trade_type'].iloc[0],
                                                    "order_type": category,
                                                    "symbol": symbol,
                                                    "side": side,
                                                    'type': 'averaging',
                                                    'depends_on': depends,
                                                }

                                                await positions_op.upsert_position(pos)
                                                print('Добавлен', orderLinkId)

                                if side == 'Sell':
                                    print(prev_price, current_price)
                                    if prev_price > current_price:
                                        print('No averaging for sell - linears only')
                                    else:
                                        print('lets check averaging details for short - linears only')
                                        per_cent = abs(current_price - prev_price) / prev_price * 100
                                        if per_cent >= averaging_step:
                                            print(f'lets sell extra {extra_volume}')

                                            trade_type = user['trade_type'].iloc[0]
                                            print(trade_type)
                                            if trade_type == 'demo':
                                                api_url = order_demo_url
                                                api_key = user['demo_api_key'].iloc[0]
                                                secret_key = user['demo_secret_key'].iloc[0]
                                                orderLinkId = f"{str(row['owner_id'])}_demo_linear_aver_{uuid.uuid4().hex[:8]}"
                                                print('orderLinkId', orderLinkId)
                                            else:
                                                api_url = order_trade_url
                                                api_key = user['main_api_key'].iloc[0]
                                                print('api_key', api_key)
                                                secret_key = user['main_secret_key'].iloc[0]
                                                print('api_key', api_key)
                                                orderLinkId = f"{str(row['owner_id'])}_real_linear_aver_{uuid.uuid4().hex[:8]}"
                                                print('orderLinkId', orderLinkId)

                                            res = await universal_market_order(api_url, str(api_key), str(secret_key), category, symbol,
                                                                          side, extra_volume, orderLinkId)
                                            print(res)
                                            if isinstance(res, dict) and res.get('retMsg') == 'OK':
                                                result = res.get('result')
                                                orderLinkId = result.get('orderLinkId')
                                                depends = row['bybit_id']
                                                pos = {
                                                    "bybit_id": orderLinkId,
                                                    "owner_id": int(row['owner_id']),
                                                    "market": user['trade_type'].iloc[0],
                                                    "order_type": category,
                                                    "symbol": symbol,
                                                    "side": side,
                                                    'type': 'averaging',
                                                    'depends_on': depends,
                                                }

                                                await positions_op.upsert_position(pos)
                                                print('Добавлен', orderLinkId)


                    except Exception as e:
                        print(f"Ошибка в блоке START AVERAGING TRADE LOGIC: {e}")
                        traceback.print_exc()

                #                    #####
                #                ############
                # ####### STOP AVERAGING TRADE LOGIC ########


            # ####### START CHECK IF PRIMARY ORDER PERFORMED ########
            #              ############
            #                 #####


            try:
                open_positions = (await positions_op.get_positions_by_fields({"orderStatus": False,}))['bybit_id'].to_list()
            except:
                open_positions = []

            positions_filled = []
            averaging_positions_filled = []
            #res_demo = {}
            #res_real = {}
            users_demo = users[users['trade_type'] == 'demo']['telegram_id'].to_list()
            for user in users_demo:
                res_one = await get_user_orders(user, user_orders_demo_url, 'spot', 1, demo=True)
                if not res_one:
                    res_one = []
                try:
                    res_one.extend(await get_user_orders(user, user_orders_demo_url, 'linear', 1, demo=True))
                except:
                    pass
                res_demo = {
                    order['orderLinkId']: {
                        'orderStatus': order['orderStatus'],
                        'avgPrice': order['avgPrice'],
                        'cumExecValue': order['cumExecValue'],
                        'cumExecQty': order['cumExecQty'],
                        'cumExecFee': order['cumExecFee'],
                        'type': order['cumExecFee'],
                    }
                    for order in res_one if order['orderStatus'] == 'Filled'
                }

                if res_demo:
                    positions_filled.append(res_demo)


            users_trade = users[users['trade_type'] != 'demo']['telegram_id'].to_list()
            for user in users_trade:
                try:
                    res_real = await get_user_orders(user, user_orders_trade_url, 'spot', 2, demo=None)
                except:
                    res_real = []
                if not res_real:
                    res_real = []
                try:
                    res_real.extend(await get_user_orders(user, user_orders_trade_url, 'linear', 2, demo=None))
                except:
                    pass

                res_real = {
                    order['orderLinkId']: {
                        'orderStatus': order['orderStatus'],
                        'avgPrice': order['avgPrice'],
                        'cumExecValue': order['cumExecValue'],
                        'cumExecQty': order['cumExecQty'],
                        'cumExecFee': order['cumExecFee'],
                        'type': order['cumExecFee'],
                    }
                    for order in res_real if order['orderStatus'] == 'Filled'
                }

                if res_real:  # Проверяем, что res_real не пуст
                    positions_filled.append(res_real)  # Добавляем копию словаря

            if positions_filled:
                for open_position in open_positions:
                    # Проверяем, есть ли open_position в ключах словаря positions_filled
                    if open_position in positions_filled[0]:
                        # Извлекаем данные из positions_filled для данного open_position
                        position_data = {
                            "bybit_id": open_position,
                            "orderStatus": True,
                            "avgPrice": positions_filled[0][open_position]['avgPrice'],
                            "cumExecValue": positions_filled[0][open_position]['cumExecValue'],
                            "cumExecQty": positions_filled[0][open_position]['cumExecQty'],
                            "cumExecFee": positions_filled[0][open_position]['cumExecFee'],
                        }
                        print(positions_filled[0][open_position])
                        # if positions_filled[0][open_position]['type'] == 'averaging':
                        #     averaging_positions_filled.append(position_data)
                        #     print('Закрылась позиция averaging - рассчитать и изменить основной ордер, позицию удалить')
                        #     print(open_position)
                        #else:
                        await positions_op.upsert_position(position_data)
            try:
                avg_positions = await positions_op.get_positions_by_fields({"type": "averaging", })
                for index, avg_position in avg_positions.iterrows():
                    moth_position_id = avg_position['depends_on']
                    avg_exec_value = avg_position['cumExecValue']
                    avg_exec_qty = avg_position['cumExecQty']
                    moth_position = await positions_op.get_position_by_bybit_id(moth_position_id)
                    cum_exec_value = float(moth_position['cumExecValue']) + float(avg_exec_value)
                    cum_exec_qty = float(moth_position['cumExecQty']) + float(avg_exec_qty)
                    cum_exec_price = cum_exec_value / cum_exec_qty
                    cum_exec_fee = str(f"{float(avg_position['cumExecFee']) + float(moth_position['cumExecFee']):.8f}")
                    # cum_exec_fee = float(avg_position['cumExecFee']) + float(moth_position['cumExecFee'])
                    position_data = {
                        "bybit_id": moth_position_id,
                        "avgPrice": str(cum_exec_price),
                        "cumExecValue": str(cum_exec_value),
                        "cumExecQty": str(cum_exec_qty),
                        "cumExecFee": cum_exec_fee
                    }
                    await positions_op.upsert_position(position_data)
                    await positions_op.delete_position_by_bybit_id(avg_positions["bybit_id"].iloc[0])


            except Exception as e:
                print('Oшибка при обработке усредняющих позиций', e)
                pass

                #                    #####
                #                ############
                # ####### STOP CHECK IF PRIMARY ORDER PERFORMED ########

            await asyncio.sleep(1)

        except Exception as e:
            print(f"Ошибка в trade_performance: {e}")
            traceback.print_exc()
            await asyncio.sleep(1)



async def tp_execution(database_url, price_queue):
    positions_op = PositionsOperations(database_url)
    users_op = UsersOperations(database_url)
    spot_set_op = SpotPairsOperations(database_url)
    lin_set_op = LinearPairsOperations(database_url)
    while True:


        # ####### CHECK FIRST TP CONDITION ########
        #               ############
        #                   #####
        users = await users_op.get_all_users_data()
        spot_data = await spot_set_op.get_all_spot_pairs_data()
        linear_data = await lin_set_op.get_all_linear_pairs_data()

        tasks = []
        try:
            closed_positions_no_tp = (await positions_op.get_positions_by_fields(
                {'orderStatus': True, 'tp_opened': False, 'depends_on': '-1',
                }))

            if closed_positions_no_tp.empty:
                # print('No fresh positions closed')
                await asyncio.sleep(1)
                continue

            spot_prices, linear_prices = price_queue.get()
            closed_positions_no_tp = closed_positions_no_tp[['owner_id', 'symbol', 'side',
                                                             'bybit_id', 'avgPrice', 'cumExecQty',
                                                             'order_type', 'cumExecQty', 'market']]

            for index, row in closed_positions_no_tp.iterrows():
                user = users[users['telegram_id'] == row['owner_id']]
                # print(user['tp_min'].iloc[0])

                if row['order_type'] == 'linear':
                    current_price = float(linear_prices.get(row['symbol']))
                else:
                    current_price = float(spot_prices.get(row['symbol']))
                prev_price = float(row['avgPrice'])

                x = user['tp_min'].iloc[0]

                if row['side'] == 'Buy':
                    tp_side = 'Sell'
                    # print(3, 'Ищем сигнал на закрытие лонга')

                    if current_price >= (prev_price * (1 + x / 100)):
                        # print(f"Текущая цена  {current_price} на {x}% или больше превышает цену покупки {prev_price}. Пора ТП на ЛОНГ {row['symbol']}")
                        qty_info = row['cumExecQty'].iloc[0]
                        trade_type = row['market']   # demo/real
                        order_type = row['order_type']  # spot/linear
                        symbol = row['symbol']

                        if order_type == 'spot':
                            spot_settings = spot_data.get(symbol[:-4])
                            price_tick = spot_settings.get('tick_size')
                        else:
                            linear_settings = linear_data.get(symbol[:-4])
                            price_tick = linear_settings.get('price_tick_size')

                        triggerPrice = current_price * (1 - (float(user['tp_step'].iloc[0])) / 100)
                        triggerPrice = round_price(triggerPrice, float(price_tick))
                        price = round_price(triggerPrice * 0.998, float(price_tick)) # for market conditional


                        #or_type = 'tp'  # tp/main/trailing_lin
                        orderLinkId = f'{user['telegram_id'].iloc[0]}_{trade_type}_{order_type}_tp_{uuid.uuid4().hex[:9]}' if user['trade_type'].iloc[0] == 'demo' else \
                                f'{user['telegram_id'].iloc[0]}_{trade_type}_{order_type}_tp_{uuid.uuid4().hex[:9]}'
                        # print(row)
                        # print(qty_info, tp_side, orderLinkId, or_type, order_type, trade_type, triggerPrice)


                        if row['order_type'] == 'linear':
                            pass
                            print('Открыть по фьючам TP на селл, первоначальн ордер был бай, ключи демо или мейн по trade_type == demo, количество', qty_info)
                            print('Материнский ордер', row)
                            if user['trade_type'].iloc[0] == 'demo':
                                demo = True
                            else:
                                demo = False
                            trailingStop = abs(current_price - triggerPrice)
                            rest = await set_tp_linears(user['telegram_id'].iloc[0], symbol, trailingStop, demo=demo)
                            print(rest, 'дальше изменяем в базе материнский ордер')
                            if isinstance(rest, dict) and (rest.get('retMsg') == 'OK' or rest.get('retMsg') == 'can not set tp/sl/ts for zero position'):
                                pos = {
                                    "bybit_id": row['bybit_id'],
                                    'tp_opened': True,
                                }
                                print('параметры для изменения в матер ордер')
                                await positions_op.upsert_position(pos)


                        if row['order_type'] == 'spot':
                            #print('Торгуем спот - первоначально был бай, теперь сел - определяем демо или нет, ключи демо или мейн по trade_type == demo')


                            tp_api_url = order_demo_url if user['trade_type'].iloc[0] == 'demo' else order_trade_url
                            tp_api_key = user['demo_api_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                                user['main_api_key'].iloc[0]
                            tp_secret_key = user['demo_secret_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                                user['main_secret_key'].iloc[0]
                            position = await universal_spot_conditional_market_order(tp_api_url , tp_api_key, tp_secret_key,
                                                  symbol, tp_side, qty_info, price,
                                                  triggerPrice, orderLinkId)



                            if isinstance(position, dict) and position.get('retMsg') == 'OK':
                                print('TP открыт', position, orderLinkId)
                                res = position.get('result')
                                orderLinkId = res.get('orderLinkId')
                                details = orderLinkId.split('_')
                                depends = row['bybit_id']
                                pos = {
                                    "bybit_id": orderLinkId,
                                    "owner_id": int(details[0]),
                                    "market": details[1],
                                    "order_type": details[2],
                                    "symbol": symbol,
                                    "side": tp_side,
                                    'type': 'tp',
                                    'depends_on': depends,
                                    'triggerPrice': str(triggerPrice),
                                }
                                # print(row['bybit_id'], 'orderLinkId_toinsert')
                                pos_change = {
                                    "bybit_id": row['bybit_id'],
                                    'tp_opened': True,
                                }
                                await positions_op.upsert_position(pos)
                                await positions_op.upsert_position(pos_change)
                            # Обновляем  позицию в базе данных


                else:
                    tp_side = 'Buy'
                    # print(3, 'Ищем сигнал на закрытие шорта')
                    signal = current_price <= (prev_price * (1 - x / 100))
                    if signal and (row['order_type'] == 'linear'):

                        print('Трейлинг стоп на фьюч открываем ИЗНАЧАЛЬНО ШОРТ?')
                        print('Материнский ордер', row)

                        # проверить что изначальный тип ордера тоже был demo или real
                        if user['trade_type'].iloc[0] == 'demo':
                            demo = True
                        else:
                            demo = False
                        symbol = row['symbol']
                        linear_settings = linear_data.get(symbol[:-4])
                        price_tick = linear_settings.get('price_tick_size')
                        price_tick = linear_settings.get('price_tick_size')
                        triggerPrice = current_price * (1 - (float(user['tp_step'].iloc[0])) / 100)
                        triggerPrice = round_price(triggerPrice, float(price_tick))
                        trailingStop = abs(current_price - triggerPrice)
                        print('Пытаемся поставить ТП фьюч')
                        rest = await set_tp_linears(user['telegram_id'].iloc[0], symbol, trailingStop, demo=demo)
                        print(rest, 'дальше изменяем в базе материнский ордер')
                        #######
                        ######
                        #####
                        ####
                        if isinstance(rest, dict) and rest.get('retMsg') == 'OK':
                            pos = {
                                "bybit_id": row['bybit_id'],
                                'tp_opened': True,
                            }
                            print('параметры для изменения в матер ордер')
                            await positions_op.upsert_position(pos)


        except Exception as e:
            print(f"Ошибка в процессе find initial tp: {e}")
            #                    #####
            #                ############
            # ####### STOP CHECK FIRST TP CONDITION ########

            # ####### CHECK TRAIL TP CONDITION ########
            #               ############
            #                   #####
        try:
            open_tp_orders = (await positions_op.get_positions_by_fields(
                {'orderStatus': False, 'type': 'tp', 'order_type': 'spot'
                 }))
            #print(open_tp_orders)

            if open_tp_orders.empty:
                # print('No open TP to check')
                await asyncio.sleep(1)
                continue
            #
            spot_prices, linear_prices = price_queue.get()
            open_tp_orders = open_tp_orders[['owner_id', 'symbol', 'side',
                                             'bybit_id', 'order_type',
                                             'triggerPrice', 'market', 'bybit_id']]


            for index, row in open_tp_orders.iterrows():
                user = users[users['telegram_id'] == row['owner_id']]

                current_price = float(spot_prices.get(row['symbol']))
                prev_price = float(row['triggerPrice'])
                if current_price > prev_price and row['side']:
                    # print('Поднимаем тейк профит спот на селл вверх')
                    symbol = row['symbol']
                    spot_settings = spot_data.get(symbol[:-4])
                    price_tick = spot_settings.get('tick_size')
                    new_triggerPrice = current_price * (1 - (float(user['tp_step'].iloc[0])) / 100)
                    new_triggerPrice = round_price(new_triggerPrice, float(price_tick))
                    if prev_price >= new_triggerPrice:
                        continue

                    new_price = round_price(new_triggerPrice * 0.998, float(price_tick))
                    #print('Price current', current_price, 'price_prev', prev_price, 'next_trigger', new_triggerPrice)
                    prev_orderLinkId = row['bybit_id'].iloc[0]


                    amend_order_url = amend_order_demo_url if user['trade_type'].iloc[0] == 'demo' else amend_order_trade_url

                    tp_api_key = user['demo_api_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                        user['main_api_key'].iloc[0]

                    tp_secret_key = user['demo_secret_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                        user['main_secret_key'].iloc[0]
                    res = await amend_spot_conditional_market_order(
                        amend_order_url, tp_api_key, tp_secret_key,
                        symbol, new_price, new_triggerPrice, prev_orderLinkId)

                    if isinstance(res, dict) and res.get('retMsg') == 'OK':
                        pos = {
                            "bybit_id": prev_orderLinkId,
                            'triggerPrice': str(new_triggerPrice),
                        }
                        await positions_op.upsert_position(pos)




        except Exception as e:
            print(f"Ошибка в процессе find trailing tp: {e}")

            #                    #####
            #                ############
            # ####### STOP CHECK TRAIL TP CONDITION ########



            # traceback.print_exc()
            await asyncio.sleep(1)  # Задержка при ошибке

        await asyncio.sleep(10)

def run_tp_execution_process(price_queue):
    asyncio.run(tp_execution(DATABASE_URL,price_queue))


async def daily_task():
    while True:
        try:
            now = datetime.now(timezone.utc)
            next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

            if now >= next_midnight:
                next_midnight += timedelta(days=1)

            print('Следующее обновление баланса в', next_midnight)

            sleep_time_until_midnight = (next_midnight - now).total_seconds()

            while sleep_time_until_midnight > 0:

                # Определяем, сколько времени можно спать до следующего шага

                try:
                    # Выполняем задачу
                    print('Выполняется каждые 5 минут или меньше')

                except Exception as e:
                    print(f"Ошибка в процессе daily_task - short tasks: {e}")

                sleep_interval = min(5*60, sleep_time_until_midnight)
                await asyncio.sleep(sleep_interval)

               # Обновляем оставшееся время до полуночи после выполнения задачи
                now = datetime.now(timezone.utc)
                sleep_time_until_midnight = (next_midnight - now).total_seconds()

                # Если оставшееся время меньше 15 минут, выходим из цикла
                if sleep_time_until_midnight <= 0:
                    break

            # Выполняем основную задачу в полночь
            print('Выполняется основная задача по обновлению PNL в 00:00:00')

            pnl_op = PNLManager(DATABASE_URL)
            users_op = UsersOperations(DATABASE_URL)
            users = await users_op.get_all_users_data()

            valid_users = []
            try:
                for index, user in users.iterrows():
                    if user.get('main_api_key') and user.get('main_secret_key'):
                        valid_users.append(user['telegram_id'])
            except Exception as e:
                print("Произошла ошибка при обработке пользователей:", e)
                print("Спорная переменная:", user)
                raise

            result = []
            for user_id in valid_users:
                try:
                    total_budget = await get_wallet_balance(user_id)
                    if total_budget != -1:
                        result.append({'user_id': user_id, 'total_budget': total_budget})
                except Exception as e:
                    print(f"Ошибка при получении баланса для пользователя {user_id}: {e}")

            for entry in result:
                await pnl_op.add_pnl_entry(entry)
        except Exception as e:
            print(f"Ошибка в блоке ежедневных задач daily tasks{e}")



def run_on_start_process():
    spot_pairs_op = SpotPairsOperations(DATABASE_URL)
    linear_pairs_op = LinearPairsOperations(DATABASE_URL)
    users_op = UsersOperations(DATABASE_URL)
    tg_channels_op = TgChannelsOperations(DATABASE_URL)
    signals_op = SignalsOperations(DATABASE_URL)
    db_positions = PositionsOperations(DATABASE_URL)

    asyncio.run(on_start(spot_pairs_op, linear_pairs_op, users_op, tg_channels_op, signals_op, db_positions))

def run_trade_performance_process(price_queue):
    while True:
        try:
            asyncio.run(trade_performance(DATABASE_URL, price_queue))
        except Exception as e:
            print(f"Ошибка в процессе trade_performance: {e}")
            time.sleep(1)

async def update_prices(price_queue):
    while True:
        try:
            spot_prices, linear_prices = await get_prices()
            if not price_queue.full():
                if not price_queue.empty():
                    price_queue.get_nowait()
                price_queue.put_nowait((spot_prices, linear_prices))
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Ошибка в процессе update_prices: {e}")
            await asyncio.sleep(1)

def run_update_prices_process(price_queue):
    asyncio.run(update_prices(price_queue))

def run_daily_task_process():
    asyncio.run(daily_task())

def main():
    # Создаем и запускаем процессы
    on_start_process = Process(target=run_on_start_process)
    trade_performance_process = Process(target=run_trade_performance_process, args=(price_queue,))
    price_update_process = Process(target=run_update_prices_process, args=(price_queue,))
    daily_task_process = Process(target=run_daily_task_process)
    tp_execution_process = Process(target=run_tp_execution_process, args=(price_queue,))

    on_start_process.start()
    trade_performance_process.start()
    price_update_process.start()
    daily_task_process.start()
    tp_execution_process.start()

    # Ожидаем завершения процессов
    on_start_process.join()
    trade_performance_process.join()
    price_update_process.join()
    daily_task_process.join()
    tp_execution_process.join()


if __name__ == "__main__":
    main()
