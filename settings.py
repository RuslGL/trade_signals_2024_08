IF_TEST = True  # true - real_trade, false - development mode


mainnet_url = 'https://api.bybit.com'
testnet_url = 'https://api-testnet.bybit.com'


ENDPOINTS = {
    # market endpoints
    'get_instruments_info': '/v5/market/instruments-info',
    'get_tick': '/v5/market/tickers',


    # trade endpoints


    # account endpoints
    'wallet-balance': '/v5/account/wallet-balance'
}

if IF_TEST:
    base_url = testnet_url
else:
    base_url = mainnet_url

if __name__ == '__main__':
    print(base_url)
