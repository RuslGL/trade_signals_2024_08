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
from api.account import get_wallet_balance

from tg.main_func import start_bot


load_dotenv()

DATABASE_URL = str(os.getenv('database_url'))

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
    while True:
        try:
            # ####### SIGNAL LOGIC STARTS HERE ########
            #               ############
            #                   #####

            signal = await signals_op.get_and_clear_all_signals()
            # get users settings coin settings etc

            if signal:
                coin = signal[next(iter(signal))]['coin']
                signal_details = (signal[next(iter(signal))]['direction'],
                                  coin,
                                  signal[next(iter(signal))]['channel_id'])

                print('New signal received', signal_details)

                #################### GATHER REQUESTS #######################
                averaging_channels = await db_tg_channels.get_all_channels()
                # USERS SETTINGS
                # positions


                print(averaging_channels)
                if signal_details[2] in averaging_channels:
                    print('Signal type - averaging')
                else:
                    print('Signal type - ordinary')

                # Example of using the price data
                spot_prices, linear_prices = price_queue.get()

                spot_price = spot_prices.get(coin.upper() + 'USDT')
                linear_price = linear_prices.get(coin.upper() + 'USDT')

                print(f"Spot price for {coin}USDT: {spot_price}")
                print(f"Linear price for {coin}USDT: {linear_price}")

            #               #####
            #           ############
            # ####### SIGNAL LOGIC ENDS HERE ########

            # ####### CHECK CURRENT POSITIONS AND TP ########
            #               ############
            #                   #####



            #                    #####
            #                ############
            # ####### STOP CHECK CURRENT POSITIONS AND TP ########

            # ####### CHECK CURRENT POSITIONS AND TP ########
            #               ############
            #                   #####


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
