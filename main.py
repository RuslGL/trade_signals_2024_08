import asyncio
import os
import time
from datetime import datetime, timedelta
from multiprocessing import Process, Queue
from dotenv import load_dotenv



from db.pairs import SpotPairsOperations, LinearPairsOperations
from db.users import UsersOperations
from db.tg_channels import TgChannelsOperations
from db.signals import SignalsOperations
from db.pnl import PNLManager

from api.market import process_spot_linear_settings, get_prices
from api.account import get_wallet_balance, find_usdt_budget
from api.utils import calculate_purchase_volume, round_price
from api.trade import universal_spot_conditional_market_order


from tg.main_func import start_bot
import code.settings as st

load_dotenv()

DATABASE_URL = str(os.getenv('database_url'))

trade_url = st.base_url
demo_url = st.demo_url

order_trade_url = trade_url + st.ENDPOINTS.get('place_order')
order_demo_url = demo_url + st.ENDPOINTS.get('place_order')

# Create a global queue to store the price data
price_queue = Queue()

async def on_start(db_spot_pairs, db_linear_pairs, db_users, db_tg_channels, db_signals):
    # Асинхронно создаем таблицы и получаем все торгуемые пары спот и фьюч с их настройками
    tasks = [
        asyncio.create_task(process_spot_linear_settings()),
        asyncio.create_task(db_spot_pairs.create_table()),
        asyncio.create_task(db_linear_pairs.create_table()),
        asyncio.create_task(db_users.create_table()),
        asyncio.create_task(db_tg_channels.create_table()),
        asyncio.create_task(db_signals.create_table()),
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
                # get positions


                print(averaging_channels)
                if signal_details[2] in averaging_channels:
                    averaging = True  # averaging trade logic
                    print('Signal type - averaging')
                else:
                    averaging = False  # main trade logic
                    print('Signal type - ordinary')

                # Example of using the price data
                spot_prices, linear_prices = price_queue.get()
                symbol = coin.upper() + 'USDT'
                spot_price = spot_prices.get(symbol)
                linear_price = linear_prices.get(symbol)

                print(f"Spot price for {symbol}: {spot_price}")
                print(f"Linear price for {symbol}: {linear_price}")

                # получаем торговые настройки для символа
                spot_settings = spot_data.get(coin.upper())
                spot_price = spot_prices.get(coin.upper() + 'USDT')
                spot_min_volume = spot_settings.get('min_order_qty')
                spot_qty_tick = spot_settings.get('base_precision')
                spot_price_tick = spot_settings.get('tick_size')


                linear_settings = linear_data.get(coin.upper())


            #               #####
            #           ############
            # ####### SIGNAL LOGIC ENDS HERE ########

            # ####### START MAIN TRADE LOGIC ########
            #              ############
            #                 #####



                if not averaging:
                    #  #### !!!!! проверить подписку
                    # проверить для спота что Buy!!!

                    print('Start main trade logic')
                    users_real_market = users[(users['trade_type'] == 'real') & (users['stop_trading'] == False)]
                    #print('real_trade', users_real_market[['username', 'telegram_id']])


                    # получаем доступные бюджеты для всех юзеро real
                    tasks = []
                    user_task_map = {}

                    for user_id in users_real_market['telegram_id'].tolist():
                        url = trade_url + st.ENDPOINTS.get('wallet-balance')
                        task = asyncio.create_task(find_usdt_budget(user_id, url))
                        tasks.append(task)
                        user_task_map[task] = user_id

                    budget_results = await asyncio.gather(*tasks)
                    budget_results = {user_task_map[task]: result for task, result in zip(tasks, budget_results)}
                    print('real market users budgets USDT', budget_results)


                    # spot - проверяем spot settings - если пустое пропускаем для поста
                    # real market only

                    for_spot_orders = {}

                    for user in users_real_market['telegram_id'].tolist():
                        # user_data = users[users['telegram_id'] == user]['min_trade']
                        sum_amount = min(float(users[users['telegram_id'] == user]['min_trade']),
                                         float(budget_results[user]))
                        # user_set = users_real_market[users_real_market['telegram_id'] == user].iloc[0]['tp_min']
                        # 1.015 в соответсвие с настройками привести
                        triggerPrice_value = round_price(float(spot_price) * 1.015, float(spot_price_tick))
                        price_value = round_price(float(spot_price) * 1.016, float(spot_price_tick))
                        qty_info = calculate_purchase_volume(sum_amount, triggerPrice_value, spot_min_volume, spot_qty_tick)

                        for_spot_orders[user] = {
                            'sum_amount': sum_amount,
                            'triggerPrice': triggerPrice_value,
                            'price': price_value,
                            'qty_info_spot': qty_info
                        }

                    for key, value in for_spot_orders.items():
                        # обернуть в таски и гэзер
                        if value.get('sum_amount') > 0:
                            #print(key, value)
                            user_info = users_real_market[users_real_market['telegram_id'] == key].iloc[0]
                            #print(user_info)
                            qty_prices = for_spot_orders.get(key)
                            print(order_trade_url, user_info['main_api_key'], user_info['main_secret_key'],
                                  symbol, 'Buy', qty_prices.get('qty_info_spot'), qty_prices.get('price'), qty_prices.get('triggerPrice')  )
                            res = await universal_spot_conditional_market_order(order_trade_url,
                                                                                user_info['main_api_key'],
                                                                                user_info['main_secret_key'],
                                                                                symbol, 'Buy',
                                                                                qty_prices.get('qty_info_spot'),
                                                                                qty_prices.get('price'),
                                                                                qty_prices.get('triggerPrice'))
                            print(res)


                    # qty_info_spot = {}
                    # triggerPrice = {}
                    # price = {}
                    #
                    #
                    # for user in users_real_market['telegram_id'].tolist():
                    #     sum_amount = min(float(users[users['telegram_id'] == user]['min_trade']), float(budget_results[user]))
                    #     triggerPrice = round_price(spot_price * 1.015, spot_price_tick)
                    #     price = round_price(spot_price * 1.016, spot_price_tick)
                    #     qty_info_spot[user] = calculate_purchase_volume(sum_amount, spot_price, spot_min_volume, spot_qty_tick)
                    #
                    #
                    #
                    #
                    # print(qty_info_spot)



                    #users_real_market_stand_set = users_real_market[(users_real_market['standart_settings'] == True)]['telegram_id'].tolist()
                    #print('users_real_market_stand_set', users_real_market_stand_set)




                    # рассчитываем объем покупки
                    # торгуем и сохраняем в позиции
                    # делаем по аналогии для demo


#####################################################


                    # print('нестандартную логику обработать отдельно')    # список монет # спот или фьюч
                    # users_real_market_nonstand_set = users_real_market[(users_real_market['standart_settings'] != True)]['telegram_id'].tolist()
                    # print('users_real_market_stand_set', users_real_market_nonstand_set)




                    users_demo = users[(users['trade_type'] == 'demo')]
                    #print('demo_trade',users_demo[['username', 'telegram_id']])
                    print('input demo logic')

            #                    #####
            #                ############
            # ####### STOP MAIN TRADE LOGIC ########


            # ####### START AVERAGING TRADE LOGIC ########
            #               ############
            #                   #####
                if averaging:
                    print('Start averaging logic')

            await asyncio.sleep(1)

        except Exception as e:
            print(f"Ошибка в trade_performance: {e}")
            await asyncio.sleep(1)


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

    asyncio.run(on_start(spot_pairs_op, linear_pairs_op, users_op, tg_channels_op, signals_op))

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

    on_start_process.start()
    trade_performance_process.start()
    price_update_process.start()
    daily_task_process.start()

    # Ожидаем завершения процессов
    on_start_process.join()
    trade_performance_process.join()
    price_update_process.join()
    daily_task_process.join()

if __name__ == "__main__":
    main()
