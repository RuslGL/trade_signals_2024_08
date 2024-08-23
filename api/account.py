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

from code.db.users import UsersOperations

load_dotenv()

DATABASE_URL = os.getenv('database_url')


def gen_signature_get(params, timestamp, api_key, secret_key):
    param_str = timestamp + api_key + '5000' + '&'.join([f'{k}={v}' for k, v in params.items()])
    return hmac.new(
        bytes(secret_key, "utf-8"), param_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()


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
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')

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


if __name__ == '__main__':

    async def main():
        telegram_id = 666038149
        user_op = UsersOperations(DATABASE_URL)
        settings = await user_op.get_user_data(telegram_id)
        tasks = [
            asyncio.create_task(get_user_positions(settings, demo=None)),
            asyncio.create_task(get_user_positions(settings, demo=True)),
        ]

        results = await asyncio.gather(*tasks)

        main_res = results[0]
        demo_res = results[1]
        if main_res:
            main_active_positions = [element.get('symbol') for element in main_res ]
        else:
            main_active_positions = []

        if demo_res:
            demo_active_positions = [element.get('symbol') for element in demo_res ]
        else:
            demo_active_positions = []

        print(main_active_positions)
        print(demo_active_positions)




        # res = await get_user_positions(settings, demo=True)
        # print(res)
        #telegram_id = 7113111974
        #main_url = st.base_url



        # #url = st.demo_url + st.ENDPOINTS.get('wallet-balance')
        #url = st.base_url + st.ENDPOINTS.get('wallet-balance')
        # #res = await get_wallet_balance(telegram_id, url)
        #res = await find_usdt_budget(telegram_id, demo=True)


        #print(res)



    asyncio.run(main())