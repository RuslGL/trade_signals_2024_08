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
    tasks = [
        asyncio.create_task(get_settings('spot')),
        asyncio.create_task(get_settings('linear'))
    ]

    results = await asyncio.gather(*tasks)

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

    linear_symbols = 'RECEIVED BUT NOT CONFIGURED'

    return spot_symbols, linear_symbols


if __name__ == '__main__':
    async def main():
        res = await process_spot_linear_settings()
        print(res[1])


    asyncio.run(main())
