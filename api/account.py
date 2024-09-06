import asyncio
import os
import sys
import time
import hmac
import hashlib
import json
from decimal import Decimal, ROUND_DOWN
import aiohttp
from dotenv import load_dotenv

import code.settings as st
from code.db.positions import PositionsOperations

from code.db.users import UsersOperations

load_dotenv()

DATABASE_URL = os.getenv('database_url')


def gen_signature_get(params, timestamp, api_key, secret_key):
    param_str = timestamp + api_key + '5000' + '&'.join([f'{k}={v}' for k, v in params.items()])
    return hmac.new(
        bytes(secret_key, "utf-8"), param_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()

def get_signature_post(data, timestamp, recv_wind, API_KEY, SECRET_KEY):
    """
    Returns signature for post request
    """
    query = f'{timestamp}{API_KEY}{recv_wind}{data}'
    return hmac.new(SECRET_KEY.encode('utf-8'), query.encode('utf-8'),
                    hashlib.sha256).hexdigest()


async def post_data(url, data, headers):
    """
    Makes asincio post request (used in post_bybit_signed)
    """
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data, headers=headers) as response:
            return await response.json()

async def post_bybit_signed(url, API_KEY, SECRET_KEY, **kwargs):
    """
    Sends signed post requests with aiohttp
    """
    timestamp = int(time.time() * 1000)
    recv_wind = 5000
    data = json.dumps({key: str(value) for key, value in kwargs.items()})
    signature = get_signature_post(data, timestamp, recv_wind, API_KEY, SECRET_KEY)
    headers = {
        'Accept': 'application/json',
        'X-BAPI-SIGN': signature,
        'X-BAPI-API-KEY': API_KEY,
        'X-BAPI-TIMESTAMP': str(timestamp),
        'X-BAPI-RECV-WINDOW': str(recv_wind)
    }

    return await post_data(
        url,
        data,
        headers)

async def get_wallet_balance(telegram_id, demo=None, coin=None):
    user_op = UsersOperations(DATABASE_URL)

    settings = await user_op.get_user_data(telegram_id)


    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        url = st.demo_url + st.ENDPOINTS.get('wallet-balance')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        url = st.base_url + st.ENDPOINTS.get('wallet-balance')

    if not api_key:
        return -1
    if not secret_key:
        return -1

    timestamp = str(int(time.time() * 1000))
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000'
    }
    params = {'accountType': 'UNIFIED'}
    if coin:
        params['coin'] = coin
    headers['X-BAPI-SIGN'] = gen_signature_get(params, timestamp, api_key, secret_key)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
        return data.get('result').get('list')[0].get('totalWalletBalance')
    except:
        return -1


async def find_usdt_budget(telegram_id, demo=False):
    user_op = UsersOperations(DATABASE_URL)

    settings = await user_op.get_user_data(telegram_id)
    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        url = st.demo_url + st.ENDPOINTS.get('wallet-balance')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        url = st.base_url + st.ENDPOINTS.get('wallet-balance')

    if not api_key:
        return -1
    if not secret_key:
        return -1

    timestamp = str(int(time.time() * 1000))
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000'
    }
    params = {'accountType': 'UNIFIED'}
    params['coin'] = 'USDT'
    headers['X-BAPI-SIGN'] = gen_signature_get(params, timestamp, api_key, secret_key)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
        return data.get('result').get('list')[0].get('coin')[0].get('walletBalance')
    except:
        return -1


async def get_user_orders(telegram_id, url, category, openOnly=0, demo=None):
    user_op = UsersOperations(DATABASE_URL)

    settings = await user_op.get_user_data(telegram_id)

    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        # new
        # url = st.demo_url + st.ENDPOINTS.get('open_orders')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        # new
        # url = st.base_url + st.ENDPOINTS.get('open_orders')


    if not api_key:
        #print('no_api')
        return []
    if not secret_key:
        #print('no_secret')
        return []

    timestamp = str(int(time.time() * 1000))
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000'
    }

    params = {
        'category': category,
        'settleCoin': 'USDT',
        'openOnly': openOnly
    }
    # if coin:
    #     params['coin'] = coin
    headers['X-BAPI-SIGN'] = gen_signature_get(params, timestamp, api_key, secret_key)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
        return data.get('result').get('list')

    except Exception as e:
        print(e)
        return []


async def get_user_positions(settings, demo=None):

    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        url = st.demo_url + st.ENDPOINTS.get('open_positions')

    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        url = st.base_url + st.ENDPOINTS.get('open_positions')

    if not api_key:
        #print('no_api')
        return []
    if not secret_key:
        #print('no_secret')
        return []

    timestamp = str(int(time.time() * 1000))
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000'
    }

    params = {
        'category': 'linear',
        #'symbol': 'TONUSDT',
        'settleCoin': 'USDT',
        'limit': 200,

    }

    headers['X-BAPI-SIGN'] = gen_signature_get(params, timestamp, api_key, secret_key)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
        #print(data)
        if data.get('retMsg') == 'OK':
            return data.get('result').get('list')
        if data.get('retMsg') == 'System error. Please try again later.':
            return -1
        else:
            return []

    except Exception as e:
        print(e)
        return []


async def get_order_by_id(telegram_id, category, orderLinkId, demo=None):

    user_op = UsersOperations(DATABASE_URL)

    settings = await user_op.get_user_data(telegram_id)

    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        # new
        url = st.demo_url + st.ENDPOINTS.get('open_orders')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        # new
        url = st.base_url + st.ENDPOINTS.get('open_orders')

    if not api_key:
        # print('no_api')
        return -1
    if not secret_key:
        # print('no_secret')
        return -1

    timestamp = str(int(time.time() * 1000))
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': '5000'
    }

    params = {
        'category': category,
        'orderLinkId': orderLinkId,

    }
    headers['X-BAPI-SIGN'] = gen_signature_get(params, timestamp, api_key, secret_key)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                data = await response.json()
        row_data = data.get('result').get('list')[0]
        return [data.get('result').get('list')[0].get('orderStatus'), row_data]

    except Exception as e:
        print(e)
        return -1


async def cancel_order_by_id(telegram_id, category, symbol, orderId, demo=None):
    user_op = UsersOperations(DATABASE_URL)
    settings = await user_op.get_user_data(telegram_id)
    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        # new
        url = st.demo_url + st.ENDPOINTS.get('cancel_order')
        print(api_key, secret_key, url)
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        # new
        url = st.base_url + st.ENDPOINTS.get('cancel_order')

    if not api_key:
        # print('no_api')
        return -1
    if not secret_key:
        # print('no_secret')
        return -1

    params = {
        'category': category,
        'orderId': orderId,
        'symbol': symbol,

    }
    try:
        return await post_bybit_signed(url, api_key, secret_key, **params)

    except Exception as e:
        print(e)
        return -1


# if __name__ == '__main__':
#
#     async def main():
#         while True:
#
#             telegram_id = 666038149
#             positions_op = PositionsOperations(DATABASE_URL)
#             open_positions_from_db = await positions_op.get_positions_by_fields(
#                 {
#                     'finished': False,
#                     'orderStatus': True,
#                     'order_type': 'linear',
#                 },)
#
#             settings ={ 'main_secret_key': 'G6d5XFZ9v8uvqxWOxNDlqgeFgQonJuMTBmyh', 'max_trade': 200.0, 'trading_pairs': [], 'username': 'Ruslan None', 'demo_api_key': 'dfzUeU1Ryl1Omz0nGc', 'spot': False, 'demo_secret_key': 'p2cvozFtkmObLgg10PPH76O7qPRb1hok63b4', 'tp_min': 0.1, 'trade_type': 'demo', 'tp_step': 0.1, 'subscription': 4881066778, 'telegram_id': 666038149, 'standart_settings': True, 'trade_pair_if': 0.1, 'averaging': True, 'stop_trading': False, 'averaging_step': 0.01, 'main_api_key': 'HGpVCtjfObgeyO0R7e', 'min_trade': 50.0, 'averaging_size': 1.5, 'max_leverage': 1.0}
#             tasks = [
#                 asyncio.create_task(get_user_positions(settings, demo=None)),
#                 asyncio.create_task(get_user_positions(settings, demo=True)),
#             ]
#
#             results = await asyncio.gather(*tasks)
#             main_res = results[0]
#             demo_res = results[1]
#             if main_res == -1 or demo_res == -1:
#                 print('Ошибка сервера - пропускаем')
#                 await asyncio.sleep(5)
#                 continue
#             if main_res:
#                 main_active_positions = [element.get('symbol') for element in main_res]
#             else:
#                 main_active_positions = []
#
#             if demo_res:
#                 demo_active_positions = [element.get('symbol') for element in demo_res]
#             else:
#                 demo_active_positions = []
#
#             all_open_api = main_active_positions + demo_active_positions
#
#
#             print(demo_active_positions)
#             print('all_open_api', telegram_id, all_open_api)
#
#             set_api = set(all_open_api)
#
#             if open_positions_from_db.empty:
#                 set_db = set()
#             else:
#                 user_open_pos_from_db = open_positions_from_db[open_positions_from_db['owner_id'] == telegram_id]
#                 set_db = set(user_open_pos_from_db['symbol'].unique())
#                 # print( telegram_id, 'set_db - 1', set_db)
#                 # print(telegram_id, 'set_api - 1', set_api)
#             #
#             not_in_api = list(set_db - set_api)
#             print('not_in_api', telegram_id, not_in_api)
#             for position in not_in_api:
#                 print('меняем finished на true', telegram_id, position)
#                 to_change = user_open_pos_from_db[user_open_pos_from_db['symbol'] == position]['bybit_id'].iloc[0]
#                 await positions_op.upsert_position({
#                     'bybit_id': to_change,
#                     'finished': True,
#                 })
#
#             await asyncio.sleep(5)
#     asyncio.run(main())