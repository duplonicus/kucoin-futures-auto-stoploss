"""
Kucoin web socket for trade data
"""
import asyncio
from kucoin_futures.client import TradeData, WsToken, UserData, MarketData
from kucoin_futures.ws_client import KucoinFuturesWsClient
from surreal_db import *
import configparser

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

async def main():

    async def callback(response):

        # Bitcoin level 2 data
        if response['topic'] == '/contractMarket/level2:XBTUSDM':
            print(f'Get XBTUSDM Ticker:{response["data"]}')

        # Bitcoin level 3 data
        elif response['topic'] == '/contractMarket/level3:XBTUSDTM':
            print(f'Get XBTUSDTM level3:{response["data"]}')

        # Active positions for symbol
        elif response['topic'] == '/contract/position:ETHUSDTM':
            print(f'Position change for ETHUSDT:{response["data"]}')

        # Trade data
        elif response['topic'] == '/contractMarket/tradeOrders':
            print(f'Trade Order:{response["data"]}')
            # Log trades to database
            event_loop.run_until_complete(await create_with_id("trades", response["data"]["tradeId"], response["data"]))
            # This didn't work until I added await in front of it. Data is in database but throws an exception
        else:
            print(f'{response["data"]}')

    client = WsToken(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
    ws_client = await KucoinFuturesWsClient.create(loop, client, callback, private=True)

    #await ws_client.subscribe('/contractMarket/level2:XBTUSDM')
    #await ws_client.subscribe('/contractMarket/level3:XBTUSDM')
    #await ws_client.subscribe('/contract/position:ETHUSDTM')

    # Listen for trade data
    await ws_client.subscribe('/contractMarket/tradeOrders')

    while True:
        await asyncio.sleep(60, loop=loop)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())