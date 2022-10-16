from kucoin_futures.client import MarketData, UserData
import configparser
import pandas as pd

""" Example strategy for Golden Cross trades """

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Kucoin REST API Wrapper Client Objects
td_client = UserData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
md_client = MarketData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')

# Options
timeframe = 15
watchlist = ['FTMUSDTM', 'VRAUSDTM'] # Add some symbols TODO: start watchlist with symbos from the symbol table

# Variables
buy_long = False
sell_short = False
ema50 = 1
ema200 = 2
long_condition = ema50 > ema200
short_condition = ema50 < ema200

# Functions
def check_condition() -> bool: 
    """ Do something to make the conditions True """
    for symbol in watchlist:
        k_lines = md_client.get_kline_data(symbol, timeframe) # Returns data for the last 200 candlesticks. See below.
        df = pd.DataFrame(k_lines)
        print(df)


        # Do some maths on the dataframe

        if long_condition is True:
            buy_trigger = True
        else:
            buy_trigger = False
        if short_condition is True:
            sell_trigger = True
        else:
            sell_trigger = False

check_condition()

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
        ],
        [ //Not sure what this part is. Don't think we need it
            1575374400000, 
            7464.37,
            8297.85,
            7273.02,
            7491.44,
            0
        ]
    ]
} """