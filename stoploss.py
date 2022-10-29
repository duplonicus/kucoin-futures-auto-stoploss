"""
Kucoin Futures automatic stoploss, trailing-stops, take-profits, and algo-trading
"""
from kucoin_futures.client import TradeData, MarketData
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

md_client = MarketData(key=api_key,
                secret=api_secret,
                passphrase=api_passphrase,
                is_sandbox=False,
                url='https://api-futures.kucoin.com')

# TODO: [KFAS-1] Argument parser

""" Options """
# Number of seconds between each loop
loop_wait = 1.5

# Number of ticks away from liquidation price for stoploss price. Must be integer >= 1.
ticks_from_liq = 2

# Enable take-profit orders at the profit_target_pcnt
take_profit = True

# Unrealized ROE percent target for take-profit order
profit_target_pcnt = 0.30

# Enable trailing stoplosses
trailing = True

# Unrealized ROE percent to begin trailing
start_trailing_pcnt = .10

# The unrealised ROE percentage for the first trailing stop
# Use a value lower than start_trailing_pcnt or the trade will be stopped out right away,
# but higher than your realized loss percent due to fees or it will close at a loss
### TODO: [KFAS-2] Calculate what this should be based on initial leverage so that it is always enough to cover fees
### It would need to be > realized PnL * 2 to break even for first stop
### Maybe I will just subtract this amount from the start trailing percent for bumped stops
trailing_pcnt = .05 # needs to be > mark_price + 2(realized_PnL)

# How much the unrealised PnL must increase to bump the stop
trailing_bump_pcnt = 0.05

# Increase in unrealized ROE percent required to bump trailing stop
# trailing_count_pcnt = .08 # TODO: Not used/needed

# Set to True after installing SurrealDB: https://surrealdb.com/
database = True
if database:
    from surreal_db import *

# Set to true after defining a strategy and setting up SurrealDB
strategy = True
if strategy:
    from strategy import *

""" Variables """
positions = td_client.get_all_position()
stops = td_client.get_open_stop_order()
symbols = []
symbols_dict = {}
initialized = False

""" Functions """
def init() -> None:
    """ Get data from surrealDB and display script name. """
    global symbols_dict, initialized
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'alphabet', 'GREEN')
    print("\033[91m{}\033[00m" .format('By Duplonicus\n'))
    if database:
        print("> Connecting to SurrealDB...")
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
    for i, position in enumerate(positions): # Have to enumerate because it's a list?
        symbols.append(positions[i]["symbol"])
    return symbols

def buy() -> None:
    if check_long_condition() is True:
        # Add code for what to do if your buy condition is True
        #td_client.create_limit_order(side='buy', symbol='', type='', price='', lever='', size='')
        return

def sell() -> None:
    if check_short_condition() is True:
        # Add code for what to do if your sell condition is True
        #td_client.create_limit_order(side='sell', symbol='', type='', price='', lever='', size='')
        return

### New code ###
### These functions return info for a given position, replaces old get_position_data function
def get_direction(pos: dict) -> str:
    """ Returns 'long' or 'short'. """
    direction = 'long' if pos['currentQty'] > 0 else 'short'
    side = 'buy' if direction == 'short' else 'sell'
    return direction

def get_leverage(pos: dict) -> int:
    """ Returns the initial leverage. """
    leverage = round(pos['realLeverage'] * (1 + pos['unrealisedRoePcnt']))
    return leverage

def get_unrealised_roe_pcnt(pos: dict) -> float:
    """ Returns the unrealised ROE percent. """
    unrealised_roe_pcnt = pos['unrealisedRoePcnt'] * 100
    return unrealised_roe_pcnt

def get_tick_size(pos: dict) -> str:
    """ Return the tick size. """
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

def get_trailing_stop_price(pos: dict, tick_size: str, lever: int):
    """ Returns a trailing stop price. """
    unrealisedRoePcnt = pos['unrealisedRoePcnt']
    # Get remainder and subract it from the unrealised ROE
    remainder = np.remainder(unrealisedRoePcnt, trailing_bump_pcnt)
    unrealisedRoePcnt = unrealisedRoePcnt - remainder
    print('remainder:', remainder)
    print('entry:', pos['avgEntryPrice'])

    print('unrealisedRoePcnt:', unrealisedRoePcnt)
    if pos['currentQty'] > 0: # Long
        price = pos['avgEntryPrice'] + (pos['avgEntryPrice'] * ((unrealisedRoePcnt - trailing_pcnt) / lever))
        price = round_to_tick_size(price, tick_size)
        return price
    elif pos['currentQty'] < 0: # Short
        price = pos['avgEntryPrice'] - (pos['avgEntryPrice'] * ((unrealisedRoePcnt - trailing_pcnt) / lever))
        price = round_to_tick_size(price, tick_size)
        return price

def cancel_stops_without_pos() -> None:
    """ Cancels stops without a position. """
    for item in stops["items"]:
            if item["symbol"] not in symbols:
                print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] No position for {item["symbol"]}! CANCELLING STOP orders...')
                td_client.cancel_all_stop_order(item["symbol"])

def round_to_tick_size(number: float | int, tick_size: float) -> float | int:
    """ Returns the number rounded to the tick_size. """
    if type(tick_size) == int:
        tick_size = float(tick_size)
    if type(tick_size) == float:
        tick_size = format(tick_size, 'f') # format as standard notation if scientific, this converts to string too
    # Remove trailing 0s that appear from prior conversion, Kucoin ins't happy if the order amount is 1.050000
    tick_size = tick_size.rstrip("0")
    num_decimals = len(tick_size.split('.')[1])
    tick_size = float(tick_size)
    return round(round(number / tick_size) * tick_size, num_decimals)

def get_far_stop_price(direction: str, liq_price: float | int, tick_size: str) -> float:
    """ Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price. """
    tick_size = float(tick_size)
    if direction == "long":
        return round_to_tick_size(liq_price + tick_size * ticks_from_liq, tick_size)
    elif direction == "short":
        return round_to_tick_size(liq_price - tick_size * ticks_from_liq, tick_size)

def add_trailing_stop(pos: dict) -> None:
    direction = 'long' if pos['currentQty'] > 0 else 'short'
    side = 'buy' if direction == 'short' else 'sell'
    trail_price = get_trailing_stop_price(pos, get_tick_size(pos), get_leverage(pos))
    amount = pos['currentQty']
    print(f'stop price: {trail_price}')
    oid = f'{pos["symbol"]}trail'
    if direction == "long":
        td_client.create_limit_order(clientOid=oid, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop='down', stopPrice=trail_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
    elif direction == "short":
        td_client.create_limit_order(clientOid=oid, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop='up', stopPrice=trail_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price

def add_far_stop(pos: dict):
    direction = get_direction(pos)
    tick_size = get_tick_size(pos)
    stop_price = get_far_stop_price(direction, pos['liquidationPrice'], tick_size)
    leverage = get_leverage(pos)
    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Submitting STOP order for {pos["symbol"]} {leverage} X {direction} position: {pos["currentQty"]} contracts @ {stop_price}')
    # Submit the stoploss order
    oid = f'{pos["symbol"]}far'
    if direction == "long":
        # 'price' and 'lever' can be 0 because 'stop' has a value. 'reduceOnly=True' or 'closeOrder=True' ensures a position won't be entered or increase. 'TP' means last traded price.
        td_client.create_limit_order(clientOid=oid, closeOrder=True, type='market', side='sell', symbol=pos['symbol'], stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=pos["currentQty"])
    elif direction == "short":
        td_client.create_limit_order(clientOid=oid, closeOrder=True, type='market', side='buy', symbol=pos['symbol'], stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=pos["currentQty"] * -1)

def check_far_stops(pos: dict):
    """ Submits far stop orders if not present. """
    tick_size = get_tick_size(pos)
    direction = get_direction(pos)
    stop_price = get_far_stop_price(direction, pos['liquidationPrice'], tick_size)
    for item in stops['items']:
        if direction == 'long':
            if item['symbol'] == pos['symbol']:
                if item['stop'] == 'down' and item['clientOid'] == f'{pos["symbol"]}far':
                    # If the liquidation price or amount of the stop is wrong, cancel and resubmit
                    if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size'] * -1: # Convert - to + and vise-versa because the stop is opposite
                        td_client.cancel_order(orderId=item['orderId'])
                        add_far_stop(pos)
        elif direction == 'short':
            if item['symbol'] == pos['symbol']:
                if item['stop'] == 'up' and item['clientOid'] == f'{pos["symbol"]}far':
                    if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size'] * -1:
                        td_client.cancel_order(orderId=item['orderId'])
                        add_far_stop(pos)

def check_trailing_stop(pos: dict):
    """ Make sure the trailing stop is correct """
    tick_size = get_tick_size(pos)
    direction = get_direction(pos)
    leverage = get_leverage(pos)
    trail_price = get_trailing_stop_price(pos, tick_size, leverage)
    for item in stops['items']:
        oid = item['clientOid']
        if direction == 'long':
            if item['symbol'] == pos['symbol']:
                if item['stop'] == 'down':
                    if float(item['stopPrice']) != trail_price and item['clientOid'] == f'{pos["symbol"]}trail':
                        td_client.cancel_order(orderId=item['orderId'])
                        add_trailing_stop(pos)
        elif direction == 'short':
            if item['symbol'] == pos['symbol']:
                if item['stop'] == 'up':
                    if float(item['stopPrice']) != trail_price and item['clientOid'] == f'{pos["symbol"]}trail':
                        td_client.cancel_order(orderId=item['orderId'])
                        add_trailing_stop(pos)

def check_pnl() -> None:
    for pos in positions:
        unrealised_roe_pcnt = get_unrealised_roe_pcnt(pos)
        direction = get_direction(pos)
        # If unrealised ROE is higher than start_trailing_pcnt
        if unrealised_roe_pcnt * 1e-2  > start_trailing_pcnt:
            if stops is None: # If stops is None don't bother checking
                add_trailing_stop(pos)
                continue
            check_trailing_stop(pos)
        # If unrealised ROE isn't high enough to trail
        else:
            if stops is None:
                add_far_stop(pos)
                continue
            check_far_stops(pos)

# Debugging
print(f"Positions: -------\\\n{get_positions()}")
print(f"Stops: -------\\\n{get_stops()}")
print(f"Symbols: -------\\\n{get_symbol_list()}")

def main():
    """ Happy Trading! """
    while True:
        # Try/Except to prevent script from stopping if 'Too Many Requests' or other exception returned from Kucoin
        # TODO: [KFAS-5] Figure out which requests are too close together though it doesn't really matter yet.. because the script will finish what it wants to do after the timeout. Or maybe it won't happen once everything is working
        try:

            if not initialized:
                init()

            get_positions()
            get_stops()
            get_symbol_list()

            if stops is not None:
                cancel_stops_without_pos() # new

            if not positions:
                print(f"> [{datetime.now().strftime('%A %d-%m-%Y, %H:%M:%S')}] No active positions... Start a trade!", end="\r")
                time.sleep(loop_wait)
                continue

            check_pnl() # new

            """ if take_profit:
                add_take_profits() """

            if strategy and long:
                buy()
            if strategy and short:
                sell()

            # Display active positions
            if positions:
                # This has to be a one-liner so it can be overwritten properly
                # TODO: [KFAS-17] Figure out a better way to print all the data to the console
                # This doesn't work when there are multiple positions
                if len(symbols) == 1:
                    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Active positions:',
                        ''.join(str(get_leverage(pos)).upper() for pos in positions), 'X', ' '.join(str(pos['symbol']) for pos in positions),
                        """ ''.join(str(pos['direction']).upper() for pos in pos_data.values()), """ ' '.join(str(pos['markPrice']) for pos in positions), '$',
                        ''.join(str(pos['currentQty']) for pos in positions), '@', ''.join(str(round(pos['unrealisedRoePcnt'] * 100, 2)) for pos in positions),
                        '% ', end='\r') # the part that's commented out can't be done without the old pos_data dict
                else:
                    print(f'> [{datetime.now().strftime("%A %Y-%m-%d, %H:%M:%S")}] Active positions: {symbols}', end='\r')

            time.sleep(loop_wait)

        except KeyboardInterrupt:
            # TODO: [KFAS-18] Don't say 'nice trades' if the PnL for the session is negative
            quote = requests.get("https://zenquotes.io/api/random").json()[0]["q"]
            print('\n', quote, "Nice trades!!! See you tomorrow... :)")
            quit()

        """ except Exception as e:
            print(e)
            pass """

if __name__ == '__main__':
    main()
