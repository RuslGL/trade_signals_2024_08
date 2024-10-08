import asyncio
import aiohttp

import code.settings as st
# export PYTHONPATH="${PYTHONPATH}:$(pwd)"


async def get_settings(category):
    """
    Returns all trading pairs and their settings.
    """
    url = st.mainnet_url + st.ENDPOINTS.get('get_instruments_info')

    params = {
        'category': category,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            return await response.json()


async def process_spot_linear_settings():

    # returns tuple of two spot + linear

    tasks = [
        asyncio.create_task(get_settings('spot')),
        asyncio.create_task(get_settings('linear'))
    ]

    results = await asyncio.gather(*tasks)
   # print(results[0].get('result').get('list')[0])

    # Process spot symbols
    spot_symbols = [
        {
            'name': element.get('symbol'),
            'short_name': element.get('symbol')[:-4],
            'base_precision': element.get('lotSizeFilter').get('basePrecision'),
            'quote_precision': element.get('lotSizeFilter').get('quotePrecision'),
            'min_order_qty': element.get('lotSizeFilter').get('minOrderQty'),
            'max_order_qty': element.get('lotSizeFilter').get('maxOrderQty'),
            'tick_size': element.get('priceFilter').get('tickSize')
        }
        for element in results[0].get('result').get('list')
        if element.get('status') == 'Trading' and element.get('quoteCoin') == 'USDT'
    ]

    # Process linear symbols
    linear_symbols = [
        {
            'name': element.get('symbol'),
            'short_name': element.get('symbol')[:-4],
            'min_leverage': element.get('leverageFilter').get('minLeverage'),
            'max_leverage': element.get('leverageFilter').get('maxLeverage'),
            'leverage_step': element.get('leverageFilter').get('leverageStep'),
            'unified_margin_trade': element.get('unifiedMarginTrade'),
            'min_price': element.get('priceFilter').get('minPrice'),
            'max_price': element.get('priceFilter').get('maxPrice'),
            'price_tick_size': element.get('priceFilter').get('tickSize'),
            'max_order_qty': element.get('lotSizeFilter').get('maxOrderQty'),
            'min_order_qty': element.get('lotSizeFilter').get('minOrderQty'),
            'qty_step': element.get('lotSizeFilter').get('qtyStep')
        }
        for element in results[1].get('result').get('list')
        if element.get('contractType') == 'LinearPerpetual' and element.get('status') == 'Trading' and element.get('quoteCoin') == 'USDT'
    ]

    return spot_symbols, linear_symbols


async def get_tickers(category):
    """
    Returns tickers on given category.
    """
    url = st.mainnet_url + st.ENDPOINTS.get('get_tick')
    # url = base_url + get_tick

    params = {
        'category': category,
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            return await response.json()


async def get_prices():
    """
    Returns all prices for spot and linear
    returns structure ({spot}, {linear})
    """

    tasks = [
        asyncio.create_task(get_tickers('spot')),
        asyncio.create_task(get_tickers('linear')),
    ]
    tasks_res = await asyncio.gather(*tasks)
    spot = {item['symbol']: item['lastPrice'] for item in tasks_res[0].get('result').get('list')}
    linear = {item['symbol']: item['lastPrice'] for item in tasks_res[1].get('result').get('list')}

    return spot, linear

async def get_announcements():

    url = st.mainnet_url + st.ENDPOINTS.get('announcements')
    params = {
        'locale': "en-US",
        'type': 'new_crypto',
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            res = (await response.json()).get('result').get('list')

        new_coins = []
        for element in res:
            an = element['title'].split()
            usdt_word = next((word for word in an if word.endswith('USDT')), None)
            if usdt_word is not None:
                new_coins.append(usdt_word)

        return new_coins


if __name__ == '__main__':
    async def main():
        res = await get_announcements()

        print(res)
    asyncio.run(main())
