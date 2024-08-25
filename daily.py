import numpy as np

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
from db.newcoins import NewPairsOperations

from api.market import process_spot_linear_settings, get_prices
from api.account import get_wallet_balance, find_usdt_budget, get_user_orders, get_user_positions
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

                    # ######## CHECK ALL LINEARS POSITIONS ########
                    #           ##########################
                    #                       ########

                    print('Выполняется каждую 1 минут или меньше')
                    print('Poluchaem otritie posizii')

                    positions_op = PositionsOperations(DATABASE_URL)
                    user_op = UsersOperations(DATABASE_URL)

                    try:
                        # по всем юзерам
                        open_positions_from_db = await positions_op.get_positions_by_fields(
                            {
                                'finished': False,
                                'orderStatus': True,
                                'order_type': 'linear',
                             },

                        )
                        # print('open_positions_from_db', open_positions_from_db)
                        all_users = [user['telegram_id'] for user in (await user_op.get_active_users())]

                        print(all_users)
                        if open_positions_from_db.empty:
                            print('no users with open positions')
                            users_with_open = []
                        else:
                            users_with_open = open_positions_from_db[('owner_id')].unique()


                        for telegram_id in all_users:
                            settings = await user_op.get_user_data(telegram_id)
                            tasks = [
                                asyncio.create_task(get_user_positions(settings, demo=None)),
                                asyncio.create_task(get_user_positions(settings, demo=True)),
                            ]

                            results = await asyncio.gather(*tasks)
                            #print('results', results)

                            main_res = results[0]
                            demo_res = results[1]
                            if main_res:
                                main_active_positions = [element.get('symbol') for element in main_res]
                            else:
                                main_active_positions = []

                            if demo_res:
                                demo_active_positions = [element.get('symbol') for element in demo_res]
                            else:
                                demo_active_positions = []
                            all_open_api = main_active_positions + demo_active_positions
                            set_api = set(all_open_api)
                            # # фильтруем общие позиции юзера, который обрабатывается в цикле
                            if open_positions_from_db.empty:
                                set_db = set()
                            else:
                                user_open_pos_from_db = open_positions_from_db[open_positions_from_db['owner_id'] == telegram_id]
                                set_db = set(user_open_pos_from_db['symbol'].unique())
                            #
                            # # Найдем элементы, которые есть в базе данных, но отсутствуют как открытые в API
                            not_in_api = list(set_db - set_api)
                            #print('Позиции которых нет среди открытых в апи - нужно закрыть в бд', not_in_api)
                            for position in not_in_api:
                                to_change = user_open_pos_from_db[user_open_pos_from_db['symbol'] == position]['bybit_id'].iloc[0]
                                print('id izmenit', to_change)
                                await positions_op.upsert_position({
                                    'bybit_id': to_change,
                                    'finished': True,
                                })

                            #
                            #
                            # Найдем элементы, которые есть в API, но отсутствуют в базе данных
                            not_in_db = list(set_api - set_db)
                            # print('Позиции которые есть на бирже но нет в БД - нужно внести и дальше обрабатывать', not_in_db)
                            for element in demo_res:
                                if element.get('symbol') in not_in_db:
                                    print('to insert demo', element.get('symbol'))
                                    location = 'demo'
                                    orderLinkId = f'{telegram_id}_{location}_linear_{uuid.uuid4().hex[:12]}'

                                    pos_data = {
                                        'bybit_id': orderLinkId,
                                        'owner_id': telegram_id,
                                        'type': 'main',
                                        'market': location,
                                        'order_type': 'linear',
                                        'symbol': element.get('symbol'),
                                        'side': element.get('side'),
                                        'orderStatus': True,
                                        'avgPrice': element.get('avgPrice'),
                                        'cumExecValue': element.get('positionValue'),
                                        'cumExecQty': element.get('size'),
                                        'cumExecFee': str(float(element.get('size')) * 0.001),
                                    }
                                    # print('vnesti v BD', pos_data)
                                    await positions_op.upsert_position(pos_data)

                            for element in main_res:
                                if element.get('symbol') in not_in_db:
                                    print('to insert main', element.get('symbol'))
                                    location = 'real'
                                    orderLinkId = f'{telegram_id}_{location}_linear_{uuid.uuid4().hex[:12]}'

                                    pos_data = {
                                        'bybit_id': orderLinkId,
                                        'owner_id': telegram_id,
                                        'type': 'main',
                                        'market': location,
                                        'order_type': 'linear',
                                        'symbol': element.get('symbol'),
                                        'side': element.get('side'),
                                        'orderStatus': True,
                                        'avgPrice': element.get('avgPrice'),
                                        'cumExecValue': element.get('positionValue'),
                                        'cumExecQty': element.get('size'),
                                        'cumExecFee': str(float(element.get('size')) * 0.001),
                                    }
                                    print('vnesti v BD' , pos_data)

                                    await positions_op.upsert_position(pos_data)
                    except Exception as e:
                        print(f"Ошибка в процессе выявления пропущенных фьючерсных позиций: {e}")
                        traceback.print_exc()
                    #                       ########
                    #           ##########################
                    # ######## FINISHED WITH CHECK ALL LINEARS POSITIONS ########



                    # ########  CHECK ALL SPOT POSITIONS ########
                    #           ##########################
                    #                       ########

                    try:
                        open_positions_from_db = await positions_op.get_positions_by_fields(
                            {
                                'finished': False,
                                'orderStatus': True,
                                'order_type': 'spot',
                                'type': 'tp'
                             },

                        )

                        for index, position in open_positions_from_db.iterrows():
                            moth_position_id = position['depends_on']
                            tp_position_id = position['bybit_id']

                            moth_data = {
                                "bybit_id": moth_position_id,
                                'finished': True,
                            }

                            tp_data = {
                                "bybit_id": tp_position_id,
                                'finished': True,
                            }

                            # print(moth_data, tp_data)
                            await positions_op.upsert_position(moth_data)
                            await positions_op.upsert_position(tp_data)

                        # print(open_positions_from_db)

                    except Exception as e:
                        print(f"Ошибка в процессе обработки полностью исполненных спотовых позиций: {e}")
                        traceback.print_exc()

                except Exception as e:

                    print(f"Ошибка в процессе daily_task - short tasks: {e}")
                    traceback.print_exc()

                # здесь меняем время сна в секундах
                sleep_interval = min(20, sleep_time_until_midnight)

                await asyncio.sleep(sleep_interval)

               # Обновляем оставшееся время до полуночи после выполнения задачи
                now = datetime.now(timezone.utc)
                sleep_time_until_midnight = (next_midnight - now).total_seconds()

                # Если оставшееся время меньше 15 минут, выходим из цикла
                if sleep_time_until_midnight <= 0:
                    break


#############
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
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Ошибка в блоке ежедневных задач daily tasks{e}")


asyncio.run(daily_task())

