import asyncio
import hashlib
import hmac
import json
import math
import os
import time

import aiohttp
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN


from code.api.utils import round_price

from code.db.users import UsersOperations
from code.db.pairs import LinearPairsOperations, SpotPairsOperations
from code.db.positions import PositionsOperations

import code.settings as st
from code.api.market import get_prices
from decimal import Decimal


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

async def close_market_order(url, api_key, secret_key, category, symbol, side, qty):
    return await post_bybit_signed(url, api_key, secret_key,
                                   orderType='Market',
                                   category=category,
                                   symbol=symbol,
                                   side=side,
                                   qty=qty,
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


async def set_close_linears(api_key, secret_key, symbol, price, demo=False):
    if demo:
        url = st.demo_url + st.ENDPOINTS.get('linear_tp')
    else:
        url = st.base_url + st.ENDPOINTS.get('linear_tp')
    try:
        res = await post_bybit_signed(url, api_key, secret_key,
                                      category='linear',
                                      symbol=symbol,
                                      tpslMode='Full',
                                      trailingStop=price,
                                      )
        return res
    except:
        return -1


#               #####
#            ############
# ####### STOP LEVERAGE FUNCTIONS ########



async def cancel_all_orders_positions(telegram_id):
    # получаем настройки по всем сеттингам для продажи
    db_linear_pairs = LinearPairsOperations(DATABASE_URL)
    #data_lin = await db_linear_pairs.get_all_linear_pairs_data()

    db_spot_pairs = SpotPairsOperations(DATABASE_URL)
    data_spot = await db_spot_pairs.get_all_spot_pairs_data()


    # получаем открытые позиции и купленную крипту
    position_op = PositionsOperations(DATABASE_URL)
    # prices = await get_prices()
    active_pos_demo = await position_op.get_positions_by_fields({
        "finished": False,
        "owner_id": telegram_id,
        "orderStatus": True,
        "type": 'main',
        "market": 'demo'

    })

    active_pos_real = await position_op.get_positions_by_fields({
        "finished": False,
        "owner_id": telegram_id,
        "orderStatus": True,
        "type": 'main',
        "market": 'real'
    })

    open_orders_demo = await position_op.get_positions_by_fields({
        "finished": False,
        "owner_id": telegram_id,
        "orderStatus": False,
        "type": 'main',
        "market": 'demo'
    })

    open_orders_real = await position_op.get_positions_by_fields({
        "finished": False,
        "owner_id": telegram_id,
        "orderStatus": True,
        "type": 'main',
        "market": 'real'
    })

    result = {}
    user_op = UsersOperations(DATABASE_URL)
    settings = await user_op.get_user_data(telegram_id)


    demo_api_key = settings.get('demo_api_key')
    demo_secret_key = settings.get('demo_secret_key')
    demo_url_orders = st.demo_url + st.ENDPOINTS.get('cancel_all_orders')
    demo_url_close = st.demo_url + st.ENDPOINTS.get('place_order')

    if demo_api_key and demo_secret_key:
        # отменяем ордеры demo фьючи
        # print('Есть демо ключи - отменяем')
        res_lin = (await post_bybit_signed(demo_url_orders, demo_api_key, demo_secret_key,
                                       category='linear', settleCoin = 'USDT',)).get('retMsg')
        # print('res_lin_demo', res_lin)
        if res_lin == 'OK':
            result['orders_linear_demo'] = 1
            if not open_orders_demo.empty:
                for index, row in open_orders_demo[open_orders_demo['order_type'] == 'linear'].iterrows():
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})
                print('1 Закрыли демо фьючи ордера')
        else:
            result['orders_linear_demo'] = 0

        # отменяем ордеры demo спот
        res_spot = (await post_bybit_signed(demo_url_orders, demo_api_key, demo_secret_key,
                                       category='spot', settleCoin = 'USDT',)).get('retMsg')
        # print('res_spot_demo', res_spot)
        if res_spot == 'OK':
            result['orders_spot_demo'] = 1
            if not open_orders_demo.empty:
                for index, row in open_orders_demo[open_orders_demo['order_type'] == 'spot'].iterrows():
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})
                print('2 Закрыли демо спот ордера')
        else:
            result['orders_spot_demo'] = 0

        # закрываем позиции и продаем крипту  demo
        for index, row in active_pos_demo.iterrows():

            # продаем спот
            if row['order_type'] == 'spot':
                spot_settings = data_spot.get(row['symbol'][:-4])
                qty_tick = Decimal(spot_settings.get('base_precision'))
                qty_info = ((Decimal(row['cumExecQty']) - Decimal(row['cumExecFee'])) // qty_tick) * qty_tick
                qty_info = qty_info.quantize(qty_tick, rounding=ROUND_DOWN)

                res = (await post_bybit_signed(demo_url_close, demo_api_key, demo_secret_key,
                                               category='spot', symbol=row['symbol'],
                                               side="Sell", orderType='Market', qty=qty_info, marketUnit='baseCoin')).get('retMsg')
                # print(res)
                if res == 'OK':
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})

            else:

                if row['side'] == "Buy":
                    side = "Sell"
                else:
                    side = "Buy"
                # закрываем позиции размещая противоположный ордер
                res = (await post_bybit_signed(demo_url_close, demo_api_key, demo_secret_key,
                                               category='linear', symbol=row['symbol'], reduceOnly='true',
                                               side=side, orderType='Market', qty=row['cumExecQty'], marketUnit='baseCoin')).get('retMsg')
                if res == 'OK':
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})


    # отменяем ордеры real
    real_api_key = settings.get('main_api_key')
    real_secret_key = settings.get('main_secret_key')
    real_url_orders = st.base_url + st.ENDPOINTS.get('cancel_all_orders')
    real_url_close = st.base_url + st.ENDPOINTS.get('place_order')
    if real_api_key and real_secret_key :
        # print('Есть реал ключи - отменяем')
        res_lin = (await post_bybit_signed(real_url_orders, real_api_key, real_secret_key,
                                           category='linear', settleCoin='USDT', )).get('retMsg')
        # print('res_lin_real', res_lin)
        if res_lin == 'OK':
            result['orders_linear_real'] = 1
            if not open_orders_real.empty:
                for index, row in open_orders_real[open_orders_demo['order_type'] == 'linear'].iterrows():
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})
        else:
            result['orders_linear_real'] = 0

        res_spot = (await post_bybit_signed(real_url_orders, real_api_key, real_secret_key,
                                            category='spot', settleCoin='USDT', )).get('retMsg')

        # print('res_spot_real', res_spot)
        if res_spot == 'OK':
            result['orders_spot_real'] = 1
            if not open_orders_real.empty:
                for index, row in open_orders_real[open_orders_demo['order_type'] == 'spot'].iterrows():
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})
        else:
            result['orders_spot_real'] = 0

        # закрываем позиции и продаем крипту  real
        for index, row in active_pos_real.iterrows():

            # продаем спот
            if row['order_type'] == 'spot':
                spot_settings = data_spot.get(row['symbol'][:-4])
                qty_tick = Decimal(spot_settings.get('base_precision'))
                qty_info = ((Decimal(row['cumExecQty']) - Decimal(row['cumExecFee'])) // qty_tick) * qty_tick
                qty_info = qty_info.quantize(qty_tick, rounding=ROUND_DOWN)

                res = (await post_bybit_signed(real_url_close, real_api_key, real_secret_key,
                                               category='spot', symbol=row['symbol'],
                                               side="Sell", orderType='Market', qty=qty_info, marketUnit='baseCoin')).get('retMsg')
                # print(res)
                if res == 'OK':
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})

            else:

                if row['side'] == "Buy":
                    side = "Sell"
                else:
                    side = "Buy"
                # закрываем позиции размещая противоположный ордер
                res = (await post_bybit_signed(real_url_close, real_api_key, real_secret_key,
                                               category='linear', symbol=row['symbol'], reduceOnly='true',
                                               side=side, orderType='Market', qty=row['cumExecQty'], marketUnit='baseCoin')).get('retMsg')
                if res == 'OK':
                    await position_op.upsert_position({'bybit_id': row['bybit_id'], 'finished': True})

    return result


if __name__ == '__main__':
    async def main():

        telegram_id = 7164230511 #1265026852 #666038149

        res = await cancel_all_orders_positions(telegram_id)
        print(res)

    asyncio.run(main())

