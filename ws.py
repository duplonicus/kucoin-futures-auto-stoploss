"""
Kucoin web socket for trade data
"""
import asyncio
from kucoin_futures.client import WsToken
from kucoin_futures.ws_client import KucoinFuturesWsClient
from surreal_db import *
import configparser
from disco import *

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Log closed positions to Discord
disco = True

# Clear session table
event_loop.run_until_complete(delete_all('session'))

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
            try:
                event_loop.run_until_complete(await create_with_id("trade", response["data"]["tradeId"], response["data"]))
                event_loop.run_until_complete(await create_with_id("session", response["data"]["tradeId"], response["data"]))
                # If positions closed...
                if response['data']['remainSize'] == '0':
                    # Log to Discord
                    if disco:
                        disco_log('Position Change', f'{response["data"]["symbol"]} Position Change')
                    # Print to console
                    print('Position Change', f'{response["data"]["symbol"]} Position Change')
            except Exception as e:
                pass

            # This didn't work until I added await in front of it. Data is in database but throws an exception
        else:
            print(f'{response["data"]}')

    client = WsToken(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
    ws_client = await KucoinFuturesWsClient.create(loop, client, callback, private=True)

    #await ws_client.subscribe('/contractMarket/level2:XBTUSDM')
    #await ws_client.subscribe('/contractMarket/level3:XBTUSDM')
    #await ws_client.subscribe('/contract/position:ETHUSDTM')

    # Listen for trade data
    try:
        # TODO: [KFAS-11] Figure out was causes the runtime error
        await ws_client.subscribe('/contractMarket/tradeOrders')
    except RuntimeError as r:
        #print(r)
        pass
    while True:
        await asyncio.sleep(60, loop=loop)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())