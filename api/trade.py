import asyncio
import hashlib
import hmac
import json
import math
import os
import time

import aiohttp
from dotenv import load_dotenv

from code.db.users import UsersOperations
from code.db.pairs import LinearPairsOperations

import code.settings as st

load_dotenv()


DATABASE_URL = str(os.getenv('database_url'))


# ####### BASE FUNCTIONS ########
#          ############
#             #####

def gen_signature_get(params, timestamp, API_KEY, SECRET_KEY):
    """
    Returns signature for get request
    """
    param_str = timestamp + API_KEY + '5000' + '&'.join(
        [f'{k}={v}' for k, v in params.items()])
    signature = hmac.new(
        bytes(SECRET_KEY, "utf-8"), param_str.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return signature


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

#               #####
#            ############
# ####### STOP BASE FUNCTIONS ########

# ####### TRADE FUNCTIONS ########
#          ############
#             #####


async def unuversal_linear_conditional_market_order(url, api_key, secret_key,
                                                    symbol, side, qty,
                                                    triggerPrice, triggerDirection,
                                                    orderLinkId):
    return await post_bybit_signed(url, api_key, secret_key,
                                   orderType='market', category='linear',
                                   symbol=symbol, side=side,
                                   qty=qty, marketUnit='baseCoin',
                                   triggerPrice=triggerPrice,
                                   triggerDirection=triggerDirection,
                                   orderLinkId=orderLinkId)


async def universal_spot_conditional_limit_order(url, api_key, secret_key,
                                                  symbol, side, qty, price,
                                                  triggerPrice, orderLinkId):
    return await post_bybit_signed(url,api_key, secret_key,
                                   orderType='Limit',
                                   category='spot',
                                   symbol=symbol,
                                   side=side,
                                   qty=qty,
                                   price=price,
                                   triggerPrice=triggerPrice,
                                   marketUnit='baseCoin',
                                   orderFilter='StopOrder',
                                   orderLinkId=orderLinkId
                                  )

async def universal_spot_conditional_market_order(url, api_key, secret_key,
                                                  symbol, side, qty,
                                                  triggerPrice, orderLinkId):
    return await post_bybit_signed(url,api_key, secret_key,
                                   orderType='Market',
                                   category='spot',
                                   symbol=symbol,
                                   side=side,
                                   qty=qty,
                                   triggerPrice=triggerPrice,
                                   marketUnit='baseCoin',
                                   orderFilter='StopOrder',
                                   orderLinkId=orderLinkId
                                  )

async def amend_spot_conditional_limit_order(url, api_key, secret_key,
                                              symbol, price,
                                              triggerPrice, orderLinkId):
    return await post_bybit_signed(url, api_key, secret_key,
                                   orderType='Limit',
                                   category='spot',
                                   symbol=symbol,
                                   price=price,
                                   triggerPrice=triggerPrice,
                                   orderLinkId=orderLinkId
                                   )

async def amend_spot_conditional_market_order(url, api_key, secret_key,
                                              symbol,
                                              triggerPrice, orderLinkId):
    return await post_bybit_signed(url, api_key, secret_key,
                                   orderType='Market',
                                   category='spot',
                                   symbol=symbol,
                                   triggerPrice=triggerPrice,
                                   orderLinkId=orderLinkId
                                   )

async def universal_market_order(url, api_key, secret_key, category, symbol, side, qty, orderLinkId):
    return await post_bybit_signed(url, api_key, secret_key,
                                   orderType='Market',
                                   category=category,
                                   symbol=symbol,
                                   side=side,
                                   qty=qty,
                                   marketUnit='baseCoin',
                                   orderLinkId=orderLinkId
                                   )

#               #####
#            ############
# ####### STOP TRADE FUNCTIONS ########

# ####### TP/SL FUNCTIONS ########
#          ############
#             #####
async def set_tp_linears(telegram_id, symbol, trailingStop, demo=False):
    user_op = UsersOperations(DATABASE_URL)
    settings = await user_op.get_user_data(telegram_id)
    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        url = st.demo_url + st.ENDPOINTS.get('linear_tp')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        url = st.base_url + st.ENDPOINTS.get('linear_tp')
    if not api_key:
        return -1
    if not secret_key:
        return -1
    try:
        #print('try')
        res = await post_bybit_signed(url, api_key, secret_key,
                                      category='linear',
                                      symbol=symbol,
                                      tpslMode='Full',
                                      trailingStop=trailingStop,
                                      )
        return res
    except:
        return -1


# ####### LEVERAGE FUNCTIONS ########
#          ############
#             #####
async def set_lev_linears(telegram_id, symbol, leverage, demo=False):
    user_op = UsersOperations(DATABASE_URL)
    settings = await user_op.get_user_data(telegram_id)

    if demo:
        api_key = settings.get('demo_api_key')
        secret_key = settings.get('demo_secret_key')
        url = st.demo_url + st.ENDPOINTS.get('set_leverage')
    else:
        api_key = settings.get('main_api_key')
        secret_key = settings.get('main_secret_key')
        url = st.base_url + st.ENDPOINTS.get('set_leverage')


    if not api_key:
        return -2
    if not secret_key:
        return -2

    try:
        res = (await post_bybit_signed(url, api_key, secret_key,
                                       category='linear',
                                       symbol=symbol,
                                       buyLeverage=leverage, # str '2'
                                       sellLeverage=leverage,
                                       )).get('retMsg')
        if res == 'leverage not modified' or res == 'OK':
            return 1
        #print(res)
        return -1

    except:
        return -1


async def set_lev_for_all_linears(telegram_id, leverage, demo=True, batch_size=8, delay=1.1):
    db_linear_pairs = LinearPairsOperations(DATABASE_URL)
    data = await db_linear_pairs.get_all_linear_pairs_data()
    symbols = [entry['name'] for entry in data.values()]

    failed_symbols = []  # Список для символов с ошибками

    # Проверяем первый символ перед выполнением батчей
    first_symbol = symbols[0]
    first_result = await set_lev_linears(telegram_id, first_symbol, leverage, demo)

    if first_result == -2:
        raise Exception(f"Ошибка - отсутсвуют API ключи. Прерывание выполнения.")
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        tasks = [set_lev_linears(telegram_id, symbol, leverage, demo) for symbol in batch]
        results = await asyncio.gather(*tasks)

        # Проверка результатов и добавление символов с ошибками
        for symbol, result in zip(batch, results):
            if result == -1:
                failed_symbols.append(symbol)
        print('Обновлены 8 символов, failed =', failed_symbols)
        await asyncio.sleep(delay)

    return failed_symbols

async def set_lev_for_all_linears_demo_plus_main(telegram_id, leverage):
    # changes leverage both on demo and main
    try:
        await set_lev_for_all_linears(telegram_id, leverage, demo=False, batch_size=8, delay=1)
        await set_lev_for_all_linears(telegram_id, leverage, demo=True, batch_size=8, delay=1)
        return True
    except:
        return False



#               #####
#            ############
# ####### STOP LEVERAGE FUNCTIONS ########

if __name__ == '__main__':
    async def main():
        async def universal_market():
            url = 'https://api-demo.bybit.com' +'/v5/order/create'
            api_key = '4AUSvuQyAZ1KgxrMvz'
            secret_key = 'WgW4gfYMK7IXJjhsr1uw2uJSTzNLKgbAr2Iy'
            return await post_bybit_signed(url, api_key, secret_key,
                                           orderType='Market',
                                           category='linear',
                                           symbol='BTCUSDT',
                                           side='Buy',
                                           qty=0.001,
                                           marketUnit='baseCoin',
                                           )


        res = await universal_market()

        print(res)





    asyncio.run(main())

