import asyncio
import os
import time
from multiprocessing import Process, Queue
from dotenv import load_dotenv

from db.pairs import SpotPairsOperations, LinearPairsOperations
from db.users import UsersOperations
from db.tg_channels import TgChannelsOperations
from db.signals import SignalsOperations

from api.market import process_spot_linear_settings, get_prices

from tg.main_func import start_bot

load_dotenv()

DATABASE_URL = str(os.getenv('database_url'))

# change for queue
averaging_channels = ['-1002223524620']

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
    tasks = [
        asyncio.create_task(db_spot_pairs.insert_spot_pairs(tasks_res[0][0])),
        asyncio.create_task(db_linear_pairs.insert_linear_pairs(tasks_res[0][1])),
    ]
    await asyncio.gather(*tasks)
    await start_bot()

async def trade_performance(database_url, price_queue):
    signals_op = SignalsOperations(database_url)

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

            await asyncio.sleep(1)

        except Exception as e:
            print(f"Ошибка в trade_performance: {e}")
            await asyncio.sleep(1)

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

def main():
    # Создаем и запускаем процессы
    on_start_process = Process(target=run_on_start_process)
    trade_performance_process = Process(target=run_trade_performance_process, args=(price_queue,))
    price_update_process = Process(target=run_update_prices_process, args=(price_queue,))

    on_start_process.start()
    trade_performance_process.start()
    price_update_process.start()

    # Ожидаем завершения процессов
    on_start_process.join()
    trade_performance_process.join()
    price_update_process.join()

if __name__ == "__main__":
    main()
