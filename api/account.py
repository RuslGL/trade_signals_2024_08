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
        if data.get('retMsg') == 'OK':
            return data.get('result').get('list')
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
#
#
#
#         # works
#         from datetime import datetime
#         positions_op = PositionsOperations(DATABASE_URL)
#
#
#         open_positions = await positions_op.get_positions_by_fields({"orderStatus": False,
#                                                                      "type": "main"})
#         if not open_positions.empty:
#             current_time = datetime.now()
#             for index, position in open_positions.iterrows():
#                 if position['market'] == 'demo':
#                     res = await get_order_by_id(position['owner_id'], position['order_type'], position['bybit_id'], demo=True)
#                 else:
#                     res = await get_order_by_id(position['owner_id'], position['order_type'], position['bybit_id'], demo=None)
#                 if res[0] == "Filled":
#                     print('Change', position['bybit_id'], position['symbol'],  'it filled')
#                     order_data = {
#                         "bybit_id": position['bybit_id'],
#                         "orderStatus": True,
#                         "avgPrice": res[1].get('avgPrice'),
#                         "cumExecValue": res[1].get('cumExecValue'),
#                         "cumExecQty": res[1].get('cumExecQty'),
#                         "cumExecFee": res[1].get('cumExecFee'),
#                     }
#                     await positions_op.upsert_position(order_data)
#                 else:
#                     created_time = datetime.fromisoformat(position['created'])
#                     time_difference = current_time - created_time
#                     difference_in_minutes = time_difference.total_seconds() / 60
#                     if difference_in_minutes >= 300:
#
#                         print('S momenta sozdaniya ordera', difference_in_minutes, position['bybit_id'], position['symbol'], "отменяем ордер")
#                         print('order_id', res[1].get('orderId'))
#                         if position['market'] == 'demo':
#                             await cancel_order_by_id(position['owner_id'], position['order_type'], position['symbol'],
#                                                                    res[1].get('orderId'), demo=True)
#                         else:
#                             await cancel_order_by_id(position['owner_id'], position['order_type'], position['symbol'],
#                                                                    res[1].get('orderId'), demo=None)
#                         order_data = {
#                             "bybit_id": position['bybit_id'],
#                             "finished": True,
#                             "orderStatus": True,
#                             "tp_opened": True,
#                         }
#                         await positions_op.upsert_position(order_data)
#
#     asyncio.run(main())