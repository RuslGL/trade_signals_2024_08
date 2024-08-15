import asyncio
import os
import time
from datetime import datetime, timedelta
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
from api.utils import calculate_purchase_volume, round_price
from api.trade import universal_spot_conditional_market_order, unuversal_linear_conditional_market_order


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

                # Example of using the price data
                spot_prices, linear_prices = price_queue.get()
                symbol = coin.upper() + 'USDT'

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

                    # Получаем доступные бюджеты для всех пользователей (real и demo)
                    tasks_budget = []
                    user_task_map = {}

                    for index, row in users.iterrows():
                        user_id = row['telegram_id']

                        if row['trade_type'] == 'demo':
                            url = demo_url + st.ENDPOINTS.get('wallet-balance')
                            task = asyncio.create_task(find_usdt_budget(user_id, url, demo=True))
                        else:
                            url = trade_url + st.ENDPOINTS.get('wallet-balance')
                            task = asyncio.create_task(find_usdt_budget(user_id, url))

                        tasks_budget.append(task)
                        user_task_map[task] = user_id

                    budget_results = await asyncio.gather(*tasks_budget)
                    budget_map = {user_task_map[task]: result for task, result in zip(tasks_budget, budget_results)}

                    tasks = []

                    # по торговой стратегии у спота могут быть только лонги
                    spot_price = spot_prices.get(coin.upper() + 'USDT')
                    if signal_details[0] == 'buy' and spot_price:
                        print('Start spot long', spot_price)

                        # Получаем спотовые торговые настройки для символа
                        spot_settings = spot_data.get(coin.upper())
                        spot_min_volume = spot_settings.get('min_order_qty')
                        spot_qty_tick = spot_settings.get('base_precision')
                        spot_price_tick = spot_settings.get('tick_size')

                        for_spot_orders = {}
                        # Создаем заказы для пользователей
                        for user_id in users_spot['telegram_id']:
                            trade_pair_if_buy = float(users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1
                            trade_pair_if_slip_buy = float(
                                users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1.002

                            sum_amount = min(float(users[users['telegram_id'] == user_id]['min_trade']),
                                             float(budget_map[user_id]))
                            trigger_price = round_price(float(spot_price) * trade_pair_if_buy, float(spot_price_tick))
                            price = round_price(float(spot_price) * trade_pair_if_slip_buy, float(spot_price_tick))
                            qty_info_spot = calculate_purchase_volume(sum_amount, spot_price, spot_min_volume,
                                                                      spot_qty_tick)

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
                            if order_data['sum_amount'] > 0:
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

                                # Создаем задачу для выполнения ордера
                                task = asyncio.create_task(
                                    universal_spot_conditional_market_order(
                                        api_url, api_key, secret_key, symbol, 'Buy',
                                        order_data['qty_info'], order_data['price'], order_data['triggerPrice'],
                                        orderLinkId
                                    )
                                )
                                tasks.append(task)

                        # Выполняем все задачи параллельно и собираем результаты
                        # results = await asyncio.gather(*tasks)
                        # print(results)

                    ###### linears
                    # по торговой стратегии у фьючей могут быть и лонги и шорты
                    linear_price = linear_prices.get(coin.upper() + 'USDT')
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
                            # print('user_set', user_set)
                            if signal_details[0] == 'buy':
                                #tp_min_buy = float(user_set['trade_pair_if']) / 100 + 1
                                tp_min_buy = float(users[users['telegram_id'] == user_id]['trade_pair_if']) / 100 + 1
                                print('tp_min_buy', tp_min_buy)
                                side = 'Buy'
                                triggerDirection = 1

                            if signal_details[0] == 'sell':
                                print('Продаем')
                                tp_min_buy = abs(float(user_set['trade_pair_if']) / 100 - 1)
                                print('tp_min_buy', tp_min_buy)
                                side = 'Sell'
                                triggerDirection = 2
                            sum_amount = min(float(user_set['min_trade']), float(budget_map[user_id]))
                            trigger_price_value = round_price(float(linear_price) * tp_min_buy,
                                                              float(linear_price_tick))
                            print('trigger_price_value', trigger_price_value)
                            qty_info = calculate_purchase_volume(sum_amount, trigger_price_value, linear_min_volume,
                                                                 linear_qty_tick)

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
                            if order_data['sum_amount'] > 0:
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

                    # Выполняем все задачи параллельно и собираем результаты

                    results = await asyncio.gather(*tasks)
                    # print(results)
                    if signal_details[0] == 'buy':
                        side = 'Buy'
                    else:
                        side = 'Sell'
                    # сохраняем исполненные в positions
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
                            await positions_op.upsert_position(pos)

                #####################################################

                #                    #####
                #                ############
                # ####### STOP MAIN TRADE LOGIC ########


                # ####### START AVERAGING TRADE LOGIC ########
                #               ############
                #                   #####
                if averaging:
                    print('Start averaging logic')

                #                    #####
                #                ############
                # ####### START AVERAGING TRADE LOGIC ########


            # ####### START CHECK IF PRIMARY ORDER PERFORMED ########
            #              ############
            #                 #####


            try:
                open_positions = (await positions_op.get_positions_by_fields({"orderStatus": False, "type": 'main',}))['bybit_id'].to_list()
            except:

                open_positions = []

            positions_filled = []
            res_demo = {}
            res_real = {}
            users_demo = users[users['trade_type'] == 'demo']['telegram_id'].to_list()
            for user in users_demo:
                res_one = await get_user_orders(user, user_orders_demo_url, 'spot', 1, demo=True)
                res_one.extend(await get_user_orders(user, user_orders_demo_url, 'linear', 1, demo=True))
                res_demo = {
                    order['orderLinkId']: {
                        'orderStatus': order['orderStatus'],
                        'avgPrice': order['avgPrice'],
                        'cumExecValue': order['cumExecValue'],
                        'cumExecQty': order['cumExecQty'],
                        'cumExecFee': order['cumExecFee']
                    }
                    for order in res_one if order['orderStatus'] == 'Filled'
                }

                if res_demo:
                    positions_filled.append(res_demo)


            users_trade = users[users['trade_type'] != 'demo']['telegram_id'].to_list()
            for user in users_trade:
                res_real = await get_user_orders(user, user_orders_trade_url, 'spot', 2, demo=None)
                res_real.extend(await get_user_orders(user, user_orders_trade_url, 'linear', 2, demo=None))

                res_real = {
                    order['orderLinkId']: {
                        'orderStatus': order['orderStatus'],
                        'avgPrice': order['avgPrice'],
                        'cumExecValue': order['cumExecValue'],
                        'cumExecQty': order['cumExecQty'],
                        'cumExecFee': order['cumExecFee']
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

                        # Обновляем  позицию в базе данных
                        await positions_op.upsert_position(position_data)

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
                {'orderStatus': True, 'tp_opened': False,
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
                print(1, 'Изменение цены', current_price - prev_price, (current_price - prev_price)/prev_price)
                print(2, row['symbol'], row['bybit_id'])

                if row['side'] == 'Buy':
                    tp_side = 'Sell'
                    print(3, 'Ищем сигнал на закрытие лонга')

                    if current_price >= (prev_price * (1 + x / 100)):
                        print(f"Текущая цена  {current_price} на {x}% или больше превышает цену покупки {prev_price}. Пора ТП на ЛОНГ {row['symbol']}")
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
                        price = round_price(triggerPrice * 0.999, float(price_tick)) # for market conditional


                        or_type = 'tp'  # tp/main/trailing_lin
                        orderLinkId = f'{user['telegram_id'].iloc[0]}_{trade_type}_{order_type}_tp_{uuid.uuid4().hex[:9]}' if user['trade_type'].iloc[0] == 'demo' else \
                                f'{user['telegram_id'].iloc[0]}_{trade_type}_{order_type}_tp_{uuid.uuid4().hex[:9]}'
                        # print(row)
                        print(qty_info, tp_side, orderLinkId, or_type, order_type, trade_type, triggerPrice)

                        if row['order_type'] == 'linear':
                            print('Это фьюч TP на селл, первоначальн ордер был бай, ключи демо или мейн по trade_type == demo')
                        if row['order_type'] == 'spot':
                            print('Торгуем спот - первоначально был бай, теперь сел - определяем демо или нет, ключи демо или мейн по trade_type == demo')


                            tp_api_url = order_demo_url if user['trade_type'].iloc[0] == 'demo' else order_trade_url
                            tp_api_key = user['demo_api_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                                user['main_api_key'].iloc[0]
                            tp_secret_key = user['demo_secret_key'].iloc[0] if user['trade_type'].iloc[0] == 'demo' else \
                                user['main_secret_key'].iloc[0]
                            position = await universal_spot_conditional_market_order(tp_api_url , tp_api_key, tp_secret_key,
                                                  symbol, tp_side, qty_info, price,
                                                  triggerPrice, orderLinkId)
                            print('TP performed', position)


                            if isinstance(position, dict) and position.get('retMsg') == 'OK':
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
                                print(row['bybit_id'], 'orderLinkId_toinsert')
                                pos_change = {
                                    "bybit_id": row['bybit_id'],
                                    'tp_opened': True,
                                }
                                await positions_op.upsert_position(pos)
                                await positions_op.upsert_position(pos_change)
                            # Обновляем  позицию в базе данных


                else:
                    tp_side = 'Buy'
                    print(3, 'Ищем сигнал на закрытие шорта')
                    signal = current_price <= (prev_price * (1 - x / 100))
                    if signal and (row['order_type'] == 'linear'):
                        print('Трейлинг стоп на фьюч открываем')



        except Exception as e:

            #                    #####
            #                ############
            # ####### STOP CHECK FIRST TP CONDITION ########
            print(f"Ошибка в процессе tp_execution: {e}")
            # traceback.print_exc()
            await asyncio.sleep(1)  # Задержка при ошибке

        await asyncio.sleep(10)

def run_tp_execution_process(price_queue):
    asyncio.run(tp_execution(DATABASE_URL,price_queue))


async def daily_task():
    while True:
        now = datetime.utcnow()
        next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if now >= next_run:
            next_run += timedelta(days=1)

        print('Следующее обновление баланса в ', next_run)

        sleep_time = (next_run - now).total_seconds()
        await asyncio.sleep(sleep_time)

        pnl_op = PNLManager(DATABASE_URL)
        users_op = UsersOperations(DATABASE_URL)
        users = await users_op.get_all_users_data()
        users = [
            user['telegram_id']
            for user in users
            if user.get('main_api_key') and user.get('main_secret_key')
        ]

        result = []
        for user in users:
            try:
                balance = await get_wallet_balance(user)
                total_budget = balance.get('totalWalletBalance')
                result.append({'user_id': user, 'total_budget': total_budget})
            except Exception as e:
                print(f"Error fetching wallet balance for user {user}: {e}")

        for entry in result:
            await pnl_op.add_pnl_entry(entry)
        print('Балансы обновлены', now)



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
