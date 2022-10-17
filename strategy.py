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
watchlist = ['FTMUSDTM', 'VRAUSDTM'] # Add some symbols TODO: start watchlist with symbols from the symbol table

long = True
short = True

# Variables
longs = {}
shorts = {}
k_line_columns = ["datetime", "open", "high", "low", "close", "volume"]
cross_up = None
cross_down = None
first_loop = True

# Functions
def check_long_condition() -> bool: 
    """ Do something to make the condition True """
    global first_loop, cross_up
    for symbol in watchlist:
        # Get k_line data from Kucoin
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below.
        # Create dataframe
        df = pd.DataFrame(k_lines)
        # Rename columns
        df.columns = k_line_columns
        # Set the index for pandas_ta functionality
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        # Get EMAs with pandas_ta
        df['Golden Cross Up'] = df.ta.ema(50, append=True) > df.ta.ema(200, append=True)
        # Return after getting first result, compare to second result on next loop, otherwise we aren't detecting the change
        if first_loop is True:
            cross_up = df.tail(1)['Golden Cross Up'].bool()
            first_loop = False
            return
        # Check if cross_up is now false
        if cross_up != df.tail(1)['Golden Cross Up'].bool():
            cross_up = not cross_up
            # Add the event to the strategy table
            try:
                event_loop.run_until_complete(create_with_id('strategy', df.tail(1)['datetime'], df.tail(1)['Golden Cross Up'].bool()))
            except Exception as e:
                # Already in DB
                pass
            return True
        else:
            return False

def check_short_condition() -> bool: 
    """ Do something to make the condition True """  
    global first_loop, cross_down
    for symbol in watchlist:
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below Example k_line data.
        df = pd.DataFrame(k_lines)
        df.columns = k_line_columns
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        df['Golden Cross Down'] = df.ta.ema(50, append=True) < df.ta.ema(200, append=True)
        if first_loop is True:
            cross_down = df.tail(1)['Golden Cross Down'].bool()
            first_loop = False
            return
        if cross_down != df.tail(1)['Golden Cross Down'].bool():
            cross_down = not cross_down
            try:
                event_loop.run_until_complete(create_with_id('strategy', df.tail(1)['datetime'], df.tail(1)['Golden Cross Up'].bool()))
            except Exception as e:
                pass
            return True
        else: 
            return False

if __name__ == '__main__':
    check_long_condition()
    check_short_condition()

""" Example k_line data:
    If neither the start time nor the end time is specified, the system will return the 200 pieces of data closest to the current time of the system.
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