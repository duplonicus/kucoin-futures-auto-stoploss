"""
Kucoin Futures automatic stoploss, trailing-stops, and algo-trading
"""
from kucoin_futures.client import TradeData, UserData, MarketData
import time
from datetime import datetime
import configparser
import requests
import pyfiglet
import numpy as np
import pandas as pd
from win10toast import ToastNotifier as toast

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Kucoin REST API Wrapper Client Objects
td_client = TradeData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
ud_client = UserData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
md_client = MarketData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')

# TODO: [KFAS-1] Argument parser

""" Options """

# Number of ticks away from liquidation price for initial stoploss
ticks_from_liq = 4
# OR set use_pcnt to True to use 'percentage to liquidation price' instead
use_pcnt = False # TODO: Finish
pcnt_to_liq = 0.90

# The get_start_trailing_pcnt() function returns the break-even percent of the position plus this percentage
# .1 is 10%
start_trailing_pcnt_lead = .10 # Example: at 20X with 0.08% fees, break even is at 3.2% ROE, add 10%, start trailing at 13.2% ROE

# The amount of leeway between the start_trailing_pcnt and the trailing stop
leeway_pcnt = .08 # Example: start trailing at 13.2% unrealised ROE, subtract 5%, trailing stop is placed at 7.2%

# How much the unrealised ROE must increase to bump the stop
trailing_bump_pcnt = .03

# The percentage of account balance normally used for trades, not used for any calculations
trade_pcnt = 0.10

# Trading fee based on VIP level
# .08 is .08%
fee = 0.08

# Set to True after installing SurrealDB: https://surrealdb.com/
database = True
if database:
    from surreal_db import *
    from sqlalchemy import create_engine, insert
    db_uri = "sqlite:///kucoin.db"
    engine = create_engine(db_uri)

# Set to True after defining a strategy
strategy = False
if strategy:
    from strategy import *


# Set to True to enable Windows toast notifications
toasty = True

# Set to True to enable Discord logging
disco = False
if disco:
    from disco import *

# Datetime format
strftime = '%A %Y-%m-%d, %H:%M:%S'

""" Global Variables """
# You can look but no touchy
positions = {}
symbols = []
stops = {}
stop_symbols = []
symbols_dict = {}
initialized = False
balance = None

# Rate limit timings
slow = 0.55 # 3/s
medium = 0.15 # 10/s

""" Functions """
def init() -> None:
    """ Get data from surrealDB and display script name. """
    global symbols_dict, initialized, balance
    balance = round(get_futures_balance(), 2)
    initialized = True
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'threepoint', 'GREEN')
    print(f"\033[91m{'By Duplonicus'}\033[00m\n")
    trail_at_pcnt = round((start_trailing_pcnt_lead - leeway_pcnt) * 1e2, 2)
    print(f'> [{datetime.now().strftime(strftime)}] Stops will be placed {ticks_from_liq} ticks away from the liquidation price')
    print(f'> [{datetime.now().strftime(strftime)}] Stops begin trailing when unrealised ROE reaches break-even plus {start_trailing_pcnt_lead * 1e2}% and increase every {trailing_bump_pcnt * 1e2}%')
    print(f'> [{datetime.now().strftime(strftime)}] With a leeway of {round(leeway_pcnt * 1e2, 2)}%, trailing stops are placed at break-even plus {trail_at_pcnt}%, {trail_at_pcnt + trailing_bump_pcnt * 1e2}%, ...')
    print(f'> [{datetime.now().strftime(strftime)}] Available Balance: {balance} USDT -> {round(trade_pcnt * 1e2)}% of Available Balance: {round(balance * trade_pcnt, 2)} USDT')
    print(f'> [{datetime.now().strftime(strftime)}] Strategy is {"Enabled" if strategy else "Disabled"}')
    if database:
        try:
            table = event_loop.run_until_complete(select_all("symbol"))
            tbl = pd.read_sql_table('symbol', engine)
            print(f'> [{datetime.now().strftime(strftime)}] Connected to SurrealDB')
        except Exception as e:
            print(f'> [{datetime.now().strftime(strftime)}]', e)
            print(f'> [{datetime.now().strftime(strftime)}] Install SurrealDB!')
            return
        if table == []:
            return
        else:
            for i, dict in enumerate(table):
                symbols_dict.update(dict)
        return
    else:
        print(f'> [{datetime.now().strftime(strftime)}] Install SurrealDB!')

def get_futures_balance() -> float:
    """ Returns the amount of USDT in the futures account. """
    overview = ud_client.get_account_overview('USDT')
    overview.update({'ts':datetime.now().strftime(strftime)})
    time.sleep(medium)
    if database:
        event_loop.run_until_complete(create_all('account', overview))
        #stmt = insert('account').values(overview)
        #engine.execute(stmt)
    return overview['availableBalance']

def get_positions() -> dict:
    """ Returns a dictionary of active futures positions. """
    global positions
    positions = td_client.get_all_position()
    time.sleep(slow) # Rate limit 9/3s
    if positions != {'code': '200000', 'data': []}:
        return positions
    else:
        positions = False
        return

def get_stops() -> dict:
    """ Returns a dictionary of active stop orders. """
    global stops
    stops = td_client.get_open_stop_order()
    time.sleep(slow) # Rate limit 10/s
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
        # Add code for what to do if the buy condition is True
        #td_client.create_limit_order(side='buy', symbol='', type='', price='', lever='', size='')
        return

def sell() -> None:
    """ Checks the short condition and places an order. """
    if check_short_condition() is True:
        # Add code for what to do if the sell condition is True
        #td_client.create_limit_order(side='sell', symbol='', type='', price='', lever='', size='')
        return

def check_strat() -> None:
    """ Calls buy() and sell(). """
    if strategy and long:
        buy()
    if strategy and short:
        sell()

def get_direction(pos: dict) -> str:
    """ Returns 'long' or 'short'. """
    direction = 'long' if pos['currentQty'] > 0 else 'short'
    return direction

def get_leverage(pos: dict) -> int:
    """ Returns the initial leverage. """
    leverage = round(pos['realLeverage'] * (1 + pos['unrealisedRoePcnt']))
    return leverage

def get_tick_size(pos: dict) -> str:
    """ Returns the tick size. """
    # Get and store symbol contract details
    if pos["symbol"] not in symbols_dict:
        symbol_data = md_client.get_contract_detail(pos["symbol"])
        time.sleep(medium)
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
    return float(tick_size)

def round_to_tick_size(number: float | int, tick_size: float | int | str) -> float:
    """ Returns the number rounded to the tick_size. """
    if type(tick_size) == int:
        tick_size = str(tick_size)
    if type(tick_size) == float:
        tick_size = format(tick_size, 'f') # Format as standard notation if scientific, this converts to string too
    tick_size = tick_size.rstrip("0") # Remove trailing 0s that appear from prior conversion
    num_decimals = len(tick_size.split('.')[1]) # Split the tick_size at the decimal, get the # of digits after
    tick_size = float(tick_size)
    rounded = round(number, num_decimals)
    rounded = round(rounded / tick_size) * tick_size # To nearest = round(num / decimal) * decimal
    rounded = round(rounded, num_decimals)
    return rounded

def get_start_trailing_pcnt(pos: dict) -> float:
    """ Returns the break-even percent + start_trailing_pcnt_lead """
    leverage = get_leverage(pos)
    start_trailing_pcnt = (fee * leverage) * 2 # The unrealised ROE % that the trade breaks even
    start_trailing_pcnt = start_trailing_pcnt * 1e-2 # Shift the decimal 2 places to the left
    start_trailing_pcnt = start_trailing_pcnt + start_trailing_pcnt_lead # Add some amount to it so that after subtracting
    return round(start_trailing_pcnt, 4)                                 # the leeway_pcnt, the first trailing stop will be in profit

def cancel_stops_without_pos() -> None:
    """ Cancels stops without a position. """
    for item in stops["items"]:
            if item["symbol"] not in symbols:
                #time.sleep(slow)
                print(f'> [{datetime.now().strftime(strftime)}] No position for {item["symbol"]}! CANCELLING STOP orders...                                      ')
                td_client.cancel_all_stop_order(item["symbol"])
                time.sleep(slow) # Rate limit 9/3s

def check_positions() -> None:
    """ Loop through positions and compare unrealised ROE % to start_trailing_pcnt. """
    for pos in positions:
        # If unrealised ROE IS high enough to start trailing, add or check trailing stop
        if pos['unrealisedRoePcnt'] > get_start_trailing_pcnt(pos):
            if pos['symbol'] not in stop_symbols:
                add_trailing_stop(pos)
                continue
            elif pos['symbol'] in stop_symbols:
                check_trailing_stop(pos)
                continue
        # If unrealised ROE IS NOT high enough to start trailing, add or check far stop
        else:
            if pos['symbol'] not in stop_symbols:
                add_far_stop(pos)
                continue
            elif pos['symbol'] in stop_symbols: # TODO: [KFAS-32] Tring to figure out why this was called after a trailing stop triggered
                check_far_stop(pos)
                continue

def check_far_stop(pos: dict) -> None:
    """ Submits far stop order if not present. """
    direction = get_direction(pos)
    stop_price = get_far_stop_price(pos)
    for item in stops['items']:
        if direction == 'long'and item['symbol'] == pos['symbol']:
            if item['stop'] == 'down' and item['clientOid'] == f'{pos["symbol"]}far':
                # If the liquidation price or amount of the stop is wrong, cancel and resubmit
                if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size']:
                    if stop_price < float(item['stopPrice']):
                        td_client.cancel_order(orderId=item['id'])
                        time.sleep(slow) # Rate limit 10/s
                        add_far_stop(pos)
                        time.sleep(slow) # Rate limit 10/s
        elif direction == 'short' and item['symbol'] == pos['symbol']:
            if item['stop'] == 'up' and item['clientOid'] == f'{pos["symbol"]}far':
                if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size']:
                    if stop_price > float(item['stopPrice']):
                        td_client.cancel_order(orderId=item['id'])
                        time.sleep(slow) # Rate limit 10/s
                        add_far_stop(pos)
                        time.sleep(slow) # Rate limit 10/s

def get_far_stop_price(pos: dict) -> float:
    """ Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price. """
    direction = get_direction(pos)
    tick_size = get_tick_size(pos)
    if direction == "long":
        if not use_pcnt:
            far_stop_price = round_to_tick_size(pos['liquidationPrice'] + (tick_size * (ticks_from_liq)), tick_size) # Add for long
            return far_stop_price
        else:
            far_stop_price = round_to_tick_size(pos['liquidationPrice'] + (tick_size * (ticks_from_liq)), tick_size) # Add for long
            return far_stop_price
    elif direction == "short":
        if not use_pcnt:
            far_stop_price = round_to_tick_size(pos['liquidationPrice'] - (tick_size * (ticks_from_liq)), tick_size) # Subract for short
            return far_stop_price

def add_far_stop(pos: dict) -> None:
    """ Adds a stop loss ticks_from_liq away from the liquidation price. """
    direction = get_direction(pos)
    stop_price = get_far_stop_price(pos)
    leverage = get_leverage(pos)
    stop = 'down' if direction == 'long' else 'up'
    side = 'buy' if direction == 'short' else 'sell'
    # Submit the stoploss order
    oId = f'{pos["symbol"]}far'
    # Lever can be 0 because stop has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    # If using type='limit', 'price' needs a value
    time.sleep(slow)
    td_client.create_limit_order(clientOid=oId, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop=stop, stopPrice=stop_price, stopPriceType='MP', price=0, lever=0, size=pos["currentQty"])
    time.sleep(slow) # Rate limit 10/s
    msg = f'> [{datetime.now().strftime(strftime)}] Submitting STOPLOSS order for {pos["symbol"]} {leverage}X {direction} position: {pos["currentQty"]} contracts @ {stop_price}'
    if toasty:
        toast.show_toast(msg, duration = 5, icon_path ="https://duplonicus.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10551?size=xxlarge")
    print(msg)
    if disco:
        disco_log('Stoploss', msg)

def check_trailing_stop(pos: dict):
    """ Make sure the trailing stop is correct, if not, cancel and resubmit. """
    direction = get_direction(pos)
    trail_price = get_trailing_stop_price(pos)
    for item in stops['items']:
        if direction == 'long' and item['symbol'] == pos['symbol'] and item['stop'] == 'down':
            if float(item['stopPrice']) < trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                time.sleep(slow)
                td_client.cancel_order(orderId=item['id'])
                time.sleep(slow) # Rate limit 10/s
                add_trailing_stop(pos)
                time.sleep(slow) # Rate limit 10/s
        elif direction == 'short' and item['symbol'] == pos['symbol'] and item['stop'] == 'up':
            if float(item['stopPrice']) > trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                time.sleep(slow)
                td_client.cancel_order(orderId=item['id'])
                time.sleep(slow) # Rate limit 10/s
                add_trailing_stop(pos)
                time.sleep(slow) # Rate limit 10/s

def get_trailing_stop_price(pos: dict) -> float:
    """ Returns a trailing stop price. """
    direction = get_direction(pos)
    tick_size = get_tick_size(pos)
    lever = get_leverage(pos)
    unrealisedRoePcnt = pos['unrealisedRoePcnt']
    # Logic for when to bump the stop, get remainder and subract it from the unrealised ROE %
    remainder = np.remainder(unrealisedRoePcnt, trailing_bump_pcnt)
    unrealisedRoePcnt = unrealisedRoePcnt - remainder
    if direction == 'long':
        #price = pos['avgEntryPrice'] + (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)) # Add for long
        price = round_to_tick_size(pos['avgEntryPrice'] + (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)), tick_size)
        return price
    elif direction == 'short':
        #price = pos['avgEntryPrice'] - (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)) # Subtract for short
        price = round_to_tick_size(pos['avgEntryPrice'] - (pos['avgEntryPrice'] * ((unrealisedRoePcnt - leeway_pcnt) / lever)), tick_size)
        return price

def add_trailing_stop(pos: dict) -> None:
    """ Adds a trailing stop. """
    direction = get_direction(pos)
    stop = 'down' if direction == 'long' else 'up'
    side = 'sell' if direction == 'long' else 'buy'
    leverage = get_leverage(pos)
    trail_price = get_trailing_stop_price(pos)
    amount = pos['currentQty']
    oId = f'{pos["symbol"]}trail'
    # Lever can be 0 because stop has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    # If using a limit order, 'price' needs a value
    time.sleep(slow) # Rate limit
    td_client.create_limit_order(clientOid=oId, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop=stop, stopPrice=trail_price, stopPriceType='MP', price=trail_price, lever=0, size=amount)
    time.sleep(slow) # Rate limit
    msg = f'> [{datetime.now().strftime(strftime)}] Submitting TRAILING STOP order for {pos["symbol"]} {leverage}X {direction} position: {pos["currentQty"]} contracts @ {trail_price} {round(pos["unrealisedRoePcnt"] * 100, 2)}%                       '
    if toasty:
        toast.show_toast(msg, duration = 5, icon_path ="https://duplonicus.atlassian.net/rest/api/2/universal_avatar/view/type/project/avatar/10551?size=xxlarge")
    print(msg)
    if disco:
        disco_log('Trailing Stop', msg)

def get_order_book(pos: dict) -> dict:
    """ Returns the order book for the position """
    book = md_client.l2_part_order_book(symbol=pos['symbol'], depth=20)
    time.sleep(medium) # Rate limit 30/3s
    return book

def get_spread(pos: dict) -> float | int:
    """ Returns the spread for the position's order book """
    book = get_order_book(pos)
    tick_size = get_tick_size(pos)
    ask = book['asks'][0][0]
    bid = book['bids'][0][0]
    spread = ask - bid
    spread = round_to_tick_size(spread, tick_size) / tick_size # Number of ticks between ask and bid
    return spread

def get_pcnt_to_liq(pos: dict) -> float:
    #TODO: This is yet to be used by anything
    """ Returns the distance to the liquidation price as a precentage. """
    liq_price = pos['liquidationPrice']
    mark_price = pos['markPrice']
    entry_price = pos['avgEntryPrice']
    full = liq_price - entry_price
    partial = liq_price - mark_price
    ptl = (partial / full) # 0.5 is 50%
    if ptl < 0:
        ptl = ptl * -1
    return ptl

def close_open_limit_orders(pos: dict) -> None:
    """ Closes open limit orders for the position """
    print(f'> [{datetime.now().strftime(strftime)}] Canceling limit orders for {pos["symbol"]}')
    td_client.cancel_all_limit_order(pos['symbol'])
    time.sleep(slow)

def get_open_limit_orders(pos: dict) -> dict:
    """ Returns open limit orders for the position """
    td_client.get_order_list(symbol=pos['symbol'], type='limit', status='active')
    time.sleep(slow)

def print_positions() -> None:
    """ Prints position info to the console """
    pos_stats = f'> [{datetime.now().strftime(strftime)}] Active Positions: ' # At the start
    for i, pos in enumerate(positions):
        pos_stats = pos_stats + f"{get_leverage(pos)}X {pos['symbol']} {get_direction(pos).upper()} {pos['currentQty']} @ {pos['avgEntryPrice']} -> {pos['markPrice']} {round(pos['unrealisedRoePcnt'] * 100, 2)}%"
        if len(symbols) > 1 and i < len(symbols) - 1: # Between items
            pos_stats = pos_stats + ' | '
    pos_stats = pos_stats + '                                             ' # At the end
    # Display the symbol list instead if 3 or more positions to try to keep it to 1 line
    if len(symbols) > 2:
        print(f"> [{datetime.now().strftime(strftime)}] Active Positions: {symbols}                                                 ", end='\r' )
        return
    print(pos_stats, end='\r')

# Debugging
""" print(f"Positions: -------\\\n{get_positions()}")
print(f"Stops: -------\\\n{get_stops()}")
print(f"Symbols: -------\\\n{get_symbol_list()}") """

def main():
    while True:
        # Try/Except to prevent script from stopping if 'Too Many Requests' or other exception returned from Kucoin or Cloudflare
        # TODO: [KFAS-5] Figure out which requests are trigging the rate limit
        try:

            if not initialized:
                init()

            get_positions()
            get_stops()
            get_symbol_list()
            get_stop_symbol_list()

            if stops is not None:
                cancel_stops_without_pos()

            if not positions:
                print(f'> [{datetime.now().strftime(strftime)}] No active positions... Start a trade!                                    ', end='\r')
                check_strat()
                continue

            check_positions()
            check_strat()

            if positions:
                print_positions()

        except KeyboardInterrupt:
            if stops is not None:
                cancel_stops_without_pos()
            end_balance = get_futures_balance()
            session_pnl = round(end_balance - balance, 2)
            quote = requests.get('https://zenquotes.io/api/random').json()[0]['q']
            if session_pnl >= 0:
                print('\n', quote, 'Nice trades! See you tomorrow...                                                        ')
            else:
                print('\n', quote, 'Those sure were some trades! See you tomorrow...                                        ')
            quit()

        except requests.exceptions.ConnectionError as e:
            print(f'> [{datetime.now().strftime(strftime)}]', 'No response!                                                                 ')
            time.sleep(slow)
            pass

        except Exception as e:
            if str(e)[:3] == '429':
                print(f'> [{datetime.now().strftime(strftime)}]', 'Kucoin 492: Too Many Requests                                            ')
            elif str(e)[:3] == '409':
                print(f'> [{datetime.now().strftime(strftime)}]', 'Cloudflare 409: DNS resolution error                                     ')
            elif str(e)[:3] == '502':
                print(f'> [{datetime.now().strftime(strftime)}]', 'Cloudflare 502                                                           ')
            elif str(e)[:3] == '500':
                print(f'> [{datetime.now().strftime(strftime)}]', 'Server Error 500                                                         ')
            else:
                print(f'> [{datetime.now().strftime(strftime)}]', e, '                                           ')
            time.sleep(slow)
            pass

if __name__ == '__main__':
    main()
