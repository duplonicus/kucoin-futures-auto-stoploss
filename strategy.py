from datetime import datetime
from kucoin_futures.client import MarketData
import configparser
import pandas as pd
import pandas_ta as ta
from surreal_db import *

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Kucoin REST API Wrapper Client Objects
md_client = MarketData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')

""" Example strategy for Golden Cross (50 EMA crossing 200 EMA) on 1 minute timeframe """

# Options
database = True
timeframe = 15
long = True # Enable longs
short = True # Enable shorts
watchlist = ('FTMUSDTM', 'VRAUSDTM')

# Variables
longs = {}
shorts = {}
cross_up = None
cross_down = None
first_check_long = True
first_check_short = True

# Constants
K_LINE_COLUMNS = ("datetime", "open", "high", "low", "close", "volume")

# Functions
def check_long_condition() -> bool:
    """ Do something to make the condition True """
    global first_check_long, cross_up
    for symbol in watchlist:
        # Get k_line data from Kucoin
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below.
        # Create dataframe
        df = pd.DataFrame(k_lines)
        # Rename columns
        df.columns = K_LINE_COLUMNS
        # Set the index for pandas_ta functionality. Not sure what requires this, just keep it.
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        # Get EMAs with pandas_ta
        df['Golden Cross Up'] = df.ta.ema(50, append=True) > df.ta.ema(200, append=True)
        # Return after getting first result, compare to second result on next loop, otherwise we aren't detecting the change
        if first_check_long is True:
            cross_up = df.tail(1)['Golden Cross Up'].bool()
            first_check_long = False
            return
        # Check if cross_up is now false
        new_cross_up = df.tail(1)['Golden Cross Up'].bool()
        if cross_up != new_cross_up:
            cross_up = new_cross_up
            print("50 EMA crossing 200 EMA UP!!")
            # Add the event to the strategy table
            try:
                if database:
                    event_loop.run_until_complete(create_all('strategy', {'name':'Golden Cross Up', 'time':datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S"), 'timeframe':timeframe}))
            except Exception as e:
                # Already in DB
                #print(e)
                pass
            return True
        else:
            return False

def check_short_condition() -> bool:
    """ Do something to make the condition True """
    global first_check_short, cross_down
    for symbol in watchlist:
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below Example k_line data.
        df = pd.DataFrame(k_lines)
        df.columns = K_LINE_COLUMNS
        df.set_index(pd.DatetimeIndex(df["datetime"]), inplace=True)
        df['Golden Cross Down'] = df.ta.ema(50, append=True) < df.ta.ema(200, append=True)
        if first_check_short is True:
            cross_down = df.tail(1)['Golden Cross Down'].bool()
            first_check_short = False
            return
        new_cross_down = df.tail(1)['Golden Cross Down'].bool()
        if cross_down != new_cross_down:
            cross_down = new_cross_down
            print("50 EMA crossing 200 EMA DOWN!!")
            if database:
                try:
                    event_loop.run_until_complete(create_all('strategy', {'name':'Golden Cross Down', 'time':datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S"), 'timeframe':timeframe}))
                except Exception:
                    pass
            return True
        else:
            return False

if __name__ == '__main__':
    check_long_condition()
    check_short_condition()

"""
Example k_line data:
    If neither the start time nor the end time is specified, the system will return the 200 pieces of data closest to the current time of the system.
    {
    "code": "200000",
    "data": [
        [
            1575331200000,#Time
            7495.01,      #Entry price
            8309.67,      #Highest price
            7250,         #Lowest price
            7463.55,      #Close price
            0             #Trading volume
        ]
    ]
    }
"""