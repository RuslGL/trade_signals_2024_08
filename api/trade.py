import asyncio
import hashlib
import hmac
import json
import math
import os
import time

import aiohttp
from dotenv import load_dotenv

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


async def universal_spot_conditional_market_order(url, api_key, secret_key,
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

#               #####
#            ############
# ####### STOP TRADE FUNCTIONS ########


# ####### TRADE STRATEGY ########
#          ############
#             #####




#               #####
#            ############
# ####### STOP TRADE STRATEGY ########


if __name__ == '__main__':
    async def main():
        pass




    asyncio.run(main())

