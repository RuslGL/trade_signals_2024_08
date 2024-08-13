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



@staticmethod
def gen_signature_get(params, timestamp, api_key, secret_key):
    param_str = timestamp + api_key + '5000' + '&'.join([f'{k}={v}' for k, v in params.items()])
    return hmac.new(
        bytes(secret_key, "utf-8"), param_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()


async def get_wallet_balance(telegram_id, url, coin=None):
    user_op = UsersOperations(DATABASE_URL)

    settings = await user_op.get_user_data(telegram_id)

    api_key = settings.get('main_api_key')
    secret_key = settings.get('main_secret_key')

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
        return data.get('result').get('list')[0]
    except:
        return -1


async def find_usdt_budget(telegram_id, url):
    balance = await get_wallet_balance(telegram_id, url, coin='USDT')
    if isinstance(balance, dict):
        return float(balance.get('totalWalletBalance', 0))
    return balance


if __name__ == '__main__':

    async def main():
        telegram_id = 666038149
        #telegram_id = 7113111974
        main_url = st.base_url



        url = st.base_url + st.ENDPOINTS.get('wallet-balance')
        #res = await get_wallet_balance(telegram_id, url)
        res = await find_usdt_budget(telegram_id, url)


        print(res)



    asyncio.run(main())