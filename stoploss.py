"""
Kucoin Futures automatic stoploss, trailing-stops, take-profits, and algo-trading
"""
from kucoin_futures.client import TradeData, UserData, MarketData
import time
from datetime import datetime
import configparser
import requests
import pyfiglet
import numpy as np

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Kucoin REST API Wrapper Client Objects
td_client = TradeData(key=api_key,
                secret=api_secret,
                passphrase=api_passphrase,
                is_sandbox=False,
                url='https://api-futures.kucoin.com')

ud_client = UserData(key=api_key,
                secret=api_secret,
                passphrase=api_passphrase,
                is_sandbox=False,
                url='https://api-futures.kucoin.com')

md_client = MarketData(key=api_key,
                secret=api_secret,
                passphrase=api_passphrase,
                is_sandbox=False,
                url='https://api-futures.kucoin.com')

# TODO: [KFAS-1] Argument parser

""" Options """
# Number of seconds between each loop
sleep_time = 1.5

# Number of ticks away from liquidation price for stoploss price. Must be integer >= 1.
ticks_from_liq = 2

# Enable take-profit orders at the profit_target_pcnt
#take_profit = True

# Unrealized ROE percent target for take-profit order
# .3 is 30%
#profit_target_pcnt = 0.30

# The get_start_trailing_pcnt() function returns the break even percent of the trade plus this percentage.
# .1 is 10%
start_trailing_pcnt_lead = .10 # Example: at 20X with 0.08% fees, break even is at 3.2% ROE, add 10%, start trailing at 13.2% ROE

# The amount of leeway between the start_trailing_pcnt and the trailing stop.
# .05 is 5%
leeway_pcnt = .05 # Example: start trailing at 13.2% ROE, trailing stop is placed at 7.2%

# How much the unrealised PnL must increase to bump the stop.
# .05 is 5%
trailing_bump_pcnt = .05

# Your trading fee based on VIP level
fee = 0.08

# Set to True after installing SurrealDB: https://surrealdb.com/
database = True
if database:
    from surreal_db import *

# Set to true after defining a strategy and setting up SurrealDB
strategy = True
if strategy:
    from strategy import *

""" Variables """
positions = {}
stops = {}
symbols_dict = {}
symbols = []
stop_symbols = []
initialized = False

""" Functions """
def init() -> None:
    """ Get data from surrealDB and display script name. """
    global symbols_dict, initialized
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'alphabet', 'GREEN')
    print("\033[91m{}\033[00m".format('By Duplonicus\n'))
    if database:
        print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Connecting to SurrealDB...')
        try:
            table = event_loop.run_until_complete(select_all("symbol"))
        except Exception as e:
            initialized = True
            print(e)
            print("> Install SurrealDB!")
            return
        if table == []:
            initialized = True
            return
        else:
            for count, dict in enumerate(table):
                symbols_dict.update(dict)
        initialized = True
        return
    else:
        initialized = True
        print("> Install SurrealDB!")

def get_futures_balance():
    overview = ud_client.get_account_overview('USDT')
    return overview['availableBalance']

def get_positions() -> dict:
    """ Returns a dictionary of active futures positions. """
    global positions
    positions = td_client.get_all_position()
    if positions != {'code': '200000', 'data': []}:
        return positions
    else:
        positions = False
        return

def get_stops() -> dict:
    """ Returns a dictionary of active stop orders. """
    global stops
    stops = td_client.get_open_stop_order()
    if stops != {'currentPage': 1, 'pageSize': 50, 'totalNum': 0, 'totalPage': 0, 'items': []}:
        return stops
    else:
        stops = None
        return None

def get_symbol_list() -> list:
    """ Returns a list of symbols from positions. """
    global symbols
    symbols = []
    if not positions:
        return symbols
    for i, position in enumerate(positions):
        symbols.append(positions[i]["symbol"])
    return symbols

def get_stop_symbol_list() -> list:
    """ Returns a list of symbols from stops. """
    global stop_symbols
    stop_symbols = []
    if stops is None:
        return stop_symbols
    for i, item in enumerate(stops['items']):
        stop_symbols.append(item["symbol"])
    return stop_symbols

def buy() -> None:
    """ Checks the long condition and places an order. """
    if check_long_condition() is True:
        # Add code for what to do if your buy condition is True
        #td_client.create_limit_order(side='buy', symbol='', type='', price='', lever='', size='')
        return

def sell() -> None:
    """ Checks the short condition and places an order. """
    if check_short_condition() is True:
        # Add code for what to do if your sell condition is True
        #td_client.create_limit_order(side='sell', symbol='', type='', price='', lever='', size='')
        return

### New code ###
### These functions return info for a given position, replaces old get_position_data function
def get_direction(pos: dict) -> str:
    """ Returns 'long' or 'short'. """
    direction = 'long' if pos['currentQty'] > 0 else 'short'
    return direction

def get_leverage(pos: dict) -> int:
    """ Returns the initial leverage. """
    leverage = round(pos['realLeverage'] * (1 + pos['unrealisedRoePcnt']))
    return leverage

def get_unrealised_roe_pcnt(pos: dict) -> float:
    """ Returns the unrealised ROE percent. """
    unrealised_roe_pcnt = pos['unrealisedRoePcnt']
    return unrealised_roe_pcnt

def get_tick_size(pos: dict) -> str:
    """ Returns the tick size. """
    # Get and store symbol contract details
    if pos["symbol"] not in symbols_dict:
        symbol_data = md_client.get_contract_detail(pos["symbol"])
        tick_size = symbol_data['tickSize']
        symbols_dict[pos["symbol"]] = symbol_data
        if database:
            try:
                # Add or update symbol data to symbol table in DB
                event_loop.run_until_complete(upsert_one("symbol", pos["symbol"], {pos["symbol"]:symbol_data}))
            except Exception as e:
                print(e)
    elif initialized:
        symbol_data = symbols_dict[pos["symbol"]]
        tick_size = symbol_data["tickSize"]
    return tick_size

def get_start_trailing_pcnt(pos: dict) -> float:
    """ Returns the break-even percent + leeway_pcnt """
    leverage = get_leverage(pos)
    start_trailing_pcnt = (fee * leverage) * 2 # This is the percentage that the trade breaks even
    start_trailing_pcnt = start_trailing_pcnt * 1e-2 # Shift the decimal 2 places to the left
    start_trailing_pcnt = start_trailing_pcnt + start_trailing_pcnt_lead # Add some amount to it so that after subtracting
    return start_trailing_pcnt                                           # the leeway_pcnt, the first trailing stop will be in profit

def cancel_stops_without_pos() -> None:
    """ Cancels stops without a position. """
    for item in stops["items"]:
            if item["symbol"] not in symbols:
                print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] No position for {item["symbol"]}! CANCELLING STOP orders...        ')
                td_client.cancel_all_stop_order(item["symbol"])

def round_to_tick_size(number: float | int, tick_size: float | int | str) -> float:
    """ Returns the number rounded to the tick_size. """
    if type(tick_size) == int:
        tick_size = str(tick_size)
    if type(tick_size) == float:
        tick_size = format(tick_size, 'f') # Format as standard notation if scientific, this converts to string too
    # Remove trailing 0s that appear from prior conversion, Kucoin ins't happy if the order amount is 1.050000
    tick_size = tick_size.rstrip("0")
    num_decimals = len(tick_size.split('.')[1])
    tick_size = float(tick_size)
    return round(round(number / tick_size) * tick_size, num_decimals)

def check_positions() -> None:
    """ Loop through positions and compare unrealised ROE to start_trailing_pcnt. """
    for pos in positions:
        unrealised_roe_pcnt = get_unrealised_roe_pcnt(pos)
        # If unrealised ROE is high enough to start trailing, add or check trailing stop
        if unrealised_roe_pcnt > get_start_trailing_pcnt(pos):
            if pos['symbol'] not in stop_symbols:
                add_trailing_stop(pos)
                continue
            check_trailing_stop(pos)
        # If unrealised ROE isn't high enough to start trailing, add or check far stop
        else:
            if pos['symbol'] not in stop_symbols:
                add_far_stop(pos)
                continue
            check_far_stop(pos)

def check_far_stop(pos: dict) -> None:
    """ Submits far stop order if not present. """
    direction = get_direction(pos)
    stop_price = get_far_stop_price(pos)
    for item in stops['items']:
        if direction == 'long'and item['symbol'] == pos['symbol']:
            if item['stop'] == 'down' and item['clientOid'] == f'{pos["symbol"]}far':
                # If the liquidation price or amount of the stop is wrong, cancel and resubmit
                if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size']:
                    td_client.cancel_order(orderId=item['id'])
                    add_far_stop(pos)
        elif direction == 'short' and item['symbol'] == pos['symbol']:
            if item['stop'] == 'up' and item['clientOid'] == f'{pos["symbol"]}far':
                if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size']:
                    td_client.cancel_order(orderId=item['id'])
                    add_far_stop(pos)

def get_far_stop_price(pos: dict) -> float:
    """ Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price. """
    direction = get_direction(pos)
    tick_size = float(get_tick_size(pos))
    if direction == "long":
        return round_to_tick_size(pos['liquidationPrice'] + tick_size * ticks_from_liq, tick_size) # Add for long
    elif direction == "short":
        return round_to_tick_size(pos['liquidationPrice'] - tick_size * ticks_from_liq, tick_size) # Subtract for short

def add_far_stop(pos: dict) -> None:
    """ Adds a stop loss ticks_from_liq away from the liquidation price. """
    direction = get_direction(pos)
    stop_price = get_far_stop_price(pos)
    leverage = get_leverage(pos)
    stop = 'down' if direction == 'long' else 'up'
    side = 'buy' if direction == 'short' else 'sell'
    # Submit the stoploss order
    oId = f'{pos["symbol"]}far'
    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Submitting STOP order for {pos["symbol"]} {leverage} X {direction} position: {pos["currentQty"]} contracts @ {stop_price}')
    # 'size' and 'lever' can be 0 because 'stop' has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    td_client.create_limit_order(clientOid=oId, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop=stop, stopPrice=stop_price, stopPriceType='MP', price=0, lever=0, size=pos["currentQty"])

def check_trailing_stop(pos: dict):
    """ Make sure the trailing stop is correct, if not, cancel and resubmit. """
    direction = get_direction(pos)
    trail_price = get_trailing_stop_price(pos)
    for item in stops['items']:
        if direction == 'long' and item['symbol'] == pos['symbol'] and item['stop'] == 'down':
            if float(item['stopPrice']) < trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                td_client.cancel_order(orderId=item['id'])
                add_trailing_stop(pos)
        elif direction == 'short' and item['symbol'] == pos['symbol'] and item['stop'] == 'up':
            if float(item['stopPrice']) > trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                td_client.cancel_order(orderId=item['id'])
                add_trailing_stop(pos)

def get_trailing_stop_price(pos: dict) -> float:
    """ Returns a trailing stop price. """
    direction = get_direction(pos)
    tick_size = get_tick_size(pos)
    lever = get_leverage(pos)
    unrealisedRoePcnt = pos['unrealisedRoePcnt']
    # Get remainder and subract it from the unrealised ROE
    remainder = np.remainder(unrealisedRoePcnt, trailing_bump_pcnt)
    unrealisedRoePcnt = unrealisedRoePcnt - remainder
    if direction == 'long':
        price = pos['avgEntryPrice'] + (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)) # Add for long
        price = round_to_tick_size(price, tick_size)
        return price
    elif direction == 'short':
        price = pos['avgEntryPrice'] - (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)) # Subtract for short
        price = round_to_tick_size(price, tick_size)
        return price

def add_trailing_stop(pos: dict) -> None:
    """ Adds a trailing stop. """
    direction = get_direction(pos)
    stop = 'down' if direction == 'long' else 'up'
    side = 'buy' if direction == 'short' else 'sell'
    leverage = get_leverage(pos)
    trail_price = get_trailing_stop_price(pos)
    amount = pos['currentQty']
    oid = f'{pos["symbol"]}trail'
    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Submitting TRAILING STOP order for {pos["symbol"]} {leverage} X {direction} position: {pos["currentQty"]} contracts @ {trail_price}')
    # Size and lever can be 0 because stop has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    td_client.create_limit_order(clientOid=oid, closeOrder=True, type='limit', side=side, symbol=pos['symbol'], stop=stop, stopPrice=trail_price, stopPriceType='MP', price=0, lever=0, size=amount)

# Debugging
""" print(f"Positions: -------\\\n{get_positions()}")
print(f"Stops: -------\\\n{get_stops()}")
print(f"Symbols: -------\\\n{get_symbol_list()}") """

def main():
    """ Happy Trading! """
    while True:
        # Try/Except to prevent script from stopping if 'Too Many Requests' or other exception returned from Kucoin
        # TODO: [KFAS-5] Figure out which requests are too close together though it doesn't really matter yet.. because the script will finish what it wants to do after the timeout. Or maybe it won't happen once everything is working
        try:

            if not initialized:
                init()
                print(f'> [{datetime.now().strftime("%A %d-%m-%Y, %H:%M:%S")}] Stops will begin trailing dynamically depending on leverage with a leeway of {leeway_pcnt * 100}%')
                balance = get_futures_balance()
                print(f'Account Balance: {balance} USDT, 10% of Account Balance: {balance * 1e-1}')

            get_positions()
            get_stops()
            get_symbol_list()
            get_stop_symbol_list()

            if stops is not None:
                cancel_stops_without_pos()

            if not positions:
                print(f"> [{datetime.now().strftime('%A %d-%m-%Y, %H:%M:%S')}] No active positions... Start a trade!                        ", end="\r")
                time.sleep(sleep_time)
                continue

            check_positions()

            if strategy and long:
                buy()
            if strategy and short:
                sell()

            # Display active positions
            if positions:
                # This has to be a one-liner so it can be overwritten properly with end='\r'
                # TODO: [KFAS-17] Figure out a better way to print all the data to the console
                # This doesn't work when there are multiple positions
                # The extra spaces are to make sure there is no remaining text after using end='\r'
                if len(symbols) == 1:
                    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Active positions:',
                        ''.join(str(get_leverage(pos)).upper() for pos in positions), 'X', ' '.join(str(pos['symbol']) for pos in positions),
                        """ ''.join(str(pos['direction']).upper() for pos in pos_data.values()), """ ' '.join(str(pos['markPrice']) for pos in positions), '$',
                        ''.join(str(pos['currentQty']) for pos in positions), '@', ''.join(str(round(pos['unrealisedRoePcnt'] * 100, 2)) for pos in positions),
                        '%                                              ', end='\r') # the part that's commented out can't be done without the old pos_data dict
                else:
                    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Active positions: {symbols}                           ', end='\r')

            time.sleep(sleep_time)

        except KeyboardInterrupt:
            # TODO: [KFAS-18] Don't say 'nice trades' if the PnL for the session is negative
            cancel_stops_without_pos()
            session = event_loop.run_until_complete(select_all('session'))
            quote = requests.get("https://zenquotes.io/api/random").json()[0]["q"]
            print('\n', quote, "Nice trades!!! See you tomorrow... :)                                           ")
            quit()

        except Exception as e:
            print(e)
            time.sleep(sleep_time)
            pass

if __name__ == '__main__':
    main()
