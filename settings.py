IF_TEST = True  # true - development mode


mainnet_url = 'https://api.bybit.com'
testnet_url = 'https://api-testnet.bybit.com'
demo_url = 'https://api-demo.bybit.com'

ENDPOINTS = {
    # market endpoints
    'get_instruments_info': '/v5/market/instruments-info',
    'get_tick': '/v5/market/tickers',


    # trade endpoints
    'place_order': '/v5/order/create',
    'cancel_order': '/v5/order/cancel',
    'open_orders': '/v5/order/realtime',
    'amend_order': '/v5/order/amend',
    'linear_tp': '/v5/position/trading-stop',

    # account endpoints
    'wallet-balance': '/v5/account/wallet-balance',
    'get_orders': '/v5/order/realtime',
    'set_leverage': '/v5/position/set-leverage',
}

if IF_TEST:
    base_url = testnet_url
else:
    base_url = mainnet_url

if __name__ == '__main__':
    print(base_url)
