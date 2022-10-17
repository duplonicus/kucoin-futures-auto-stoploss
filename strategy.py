from kucoin_futures.client import MarketData, UserData
import configparser
import pandas as pd
import pandas_ta as ta
from surreal_db import *

""" Example strategy for Golden Cross (50 EMA crossing 200 EMA) trades on 1 minute timeframe """

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Kucoin REST API Wrapper Client Objects
#ud_client = UserData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
md_client = MarketData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')

# Options
timeframe = 1
watchlist = ['FTMUSDTM', 'VRAUSDTM'] # Add some symbols TODO: start watchlist with symbos from the symbol table
long = True
short = True

# Variables
longs = {}
shorts = {}
buy_long = False
sell_short = False
k_line_columns = ["datetime", "open", "high", "low", "close", "volume"]

# Functions
def check_long_condition() -> None: 
    """ Do something to make the conditions True """
    global buy_long
    for symbol in watchlist:
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below.
        df = pd.DataFrame(k_lines)
        df.columns = k_line_columns
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        df['Golden Cross'] = df.ta.ema(50, append=True) > df.ta.ema(200, append=True)
        #print(df.tail(1)['Golden Cross'])
        if df.tail(1)['Golden Cross'].bool() is False:
            golden_cross = True
            buy_long = True
            try:
                event_loop.run_until_complete(create_with_id('strategy', df.tail(1)['datetime'].to_json(), df.tail(1).to_json()))
            except Exception as e:
                print(e)
        else:
            buy_long = False

def check_short_condition() -> None: 
    """ Do something to make the conditions True """
    global sell_short    
    for symbol in watchlist:
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below Example k_line data.
        df = pd.DataFrame(k_lines)
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        df['Golden Cross'] = df.ta.ema(50, append=True) < df.ta.ema(200, append=True)
        if df.tail(1)['Golden Cross'].bool():
            sell_short = True
            golden_cross = True
            try:
                event_loop.run_until_complete(create_with_id('strategy', df.tail(1)['datetime'].to_json(), df.tail(1).to_json()))
            except Exception as e:
                print(e)
        else:
            sell_short = False  

if __name__ == '__main__':
    check_long_condition()
    check_short_condition()

""" 
If neither the start time nor the end time is specified, the system will return the 200 pieces of data closest to the current time of the system.

Example k_line data:
{
    "code": "200000",
    "data": [
        [
            1575331200000,//Time
            7495.01,      //Entry price
            8309.67,      //Highest price
            7250,         //Lowest price
            7463.55,      //Close price
            0             //Trading volume
        ]
    ]
} """