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
# Number of seconds between each loop
sleep_time = 0

# Number of ticks away from liquidation price for stoploss
ticks_from_liq = 2

# The get_start_trailing_pcnt() function returns the break even percent of the trade plus this percentage
# .1 is 10%
start_trailing_pcnt_lead = .08 # Example: at 20X with 0.08% fees, break even is at 3.2% ROE, add 10%, start trailing at 13.2% ROE

# The amount of leeway between the start_trailing_pcnt and the trailing stop
leeway_pcnt = .05 # Example: start trailing at 13.2% unrealised ROE, trailing stop is placed at 7.2%

# How much the unrealised ROE must increase to bump the stop
trailing_bump_pcnt = .02

# Trading fee based on VIP level
fee = 0.08

# The percentage of account balance normally used for trades, not used for any calculations
trade_pcnt = 0.10

# Set to True after installing SurrealDB: https://surrealdb.com/
database = True
if database:
    from surreal_db import *

# Set to True after defining a strategy
strategy = False
if strategy:
    from strategy import *

# Set to True to enable Discord logging, useful if trading on mobile
disco = True
if disco:
    from discord_webhook import DiscordWebhook, DiscordEmbed
    disco_url = config['discord']['webhook_url']
    disco_hook = DiscordWebhook(url=disco_url)

""" Variables """
positions = {}
stops = {}
symbols_dict = {}
symbols = []
stop_symbols = []
initialized = False
strftime = '%A %Y-%m-%d, %H:%M:%S'

""" Functions """
def init() -> None:
    """ Get data from surrealDB and display script name. """
    global symbols_dict, initialized
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'threepoint', 'GREEN')
    print("\033[91m{}\033[00m".format('By Duplonicus\n'))
    if database:
        print(f'> [{datetime.now().strftime(strftime)}] Connecting to SurrealDB...')
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

def disco_log(title: str, message: str) -> None:
    """ Log a message to Discord via webhook """
    embed = DiscordEmbed(title=title, description=message, color='03b2f8')
    disco_hook.add_embed(embed)
    response = disco_hook.execute()
    disco_hook.remove_embeds()

def get_futures_balance() -> float:
    """ Returns the amount of USDT in the futures account """
    overview = ud_client.get_account_overview('USDT')
    if database:
        event_loop.run_until_complete(create_all('account', overview))
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
        # Add code for what to do if the buy condition is True
        #td_client.create_limit_order(side='buy', symbol='', type='', price='', lever='', size='')
        return

def sell() -> None:
    """ Checks the short condition and places an order. """
    if check_short_condition() is True:
        # Add code for what to do if the sell condition is True
        #td_client.create_limit_order(side='sell', symbol='', type='', price='', lever='', size='')
        return

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
    start_trailing_pcnt = (fee * leverage) * 2 # The percentage that the trade breaks even
    start_trailing_pcnt = start_trailing_pcnt * 1e-2 # Shift the decimal 2 places to the left
    start_trailing_pcnt = start_trailing_pcnt + start_trailing_pcnt_lead # Add some amount to it so that after subtracting
    return round(start_trailing_pcnt, 4)                                           # the leeway_pcnt, the first trailing stop will be in profit

def cancel_stops_without_pos() -> None:
    """ Cancels stops without a position. """
    for item in stops["items"]:
            if item["symbol"] not in symbols:
                print(f'> [{datetime.now().strftime(strftime)}] No position for {item["symbol"]}! CANCELLING STOP orders...        ')
                td_client.cancel_all_stop_order(item["symbol"])

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
    rounded = round(number / tick_size) * tick_size # To nearest = round(num / decimal) * decimal
    rounded = round(number, num_decimals)
    return rounded

def check_positions() -> None:
    """ Loop through positions and compare unrealised ROE to start_trailing_pcnt. """
    for pos in positions:
        unrealised_roe_pcnt = get_unrealised_roe_pcnt(pos)
        # If unrealised ROE is high enough to start trailing, add or check trailing stop
        if unrealised_roe_pcnt > get_start_trailing_pcnt(pos):
            if pos['symbol'] not in stop_symbols:
                add_trailing_stop(pos)
                continue
            elif pos['symbol'] in stop_symbols:
                check_trailing_stop(pos)
        # If unrealised ROE isn't high enough to start trailing, add or check far stop
        else:
            if pos['symbol'] not in stop_symbols:
                add_far_stop(pos)
                continue
            elif pos['symbol'] in stop_symbols: # Tring to figure out why this was called after a trailing stop triggered
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
                    time.sleep(.1) # Rate limit
                    add_far_stop(pos)
        elif direction == 'short' and item['symbol'] == pos['symbol']:
            if item['stop'] == 'up' and item['clientOid'] == f'{pos["symbol"]}far':
                if float(item['stopPrice']) != stop_price or pos['currentQty'] != item['size']:
                    td_client.cancel_order(orderId=item['id'])
                    time.sleep(.1) # Rate limit
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
    msg = f'> [{datetime.now().strftime(strftime)}] Submitting STOPLOSS order for {pos["symbol"]} {leverage} X {direction} position: {pos["currentQty"]} contracts @ {stop_price}'
    print(msg)
    # 'size' and 'lever' can be 0 because 'stop' has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    time.sleep(.34) # Rate limit
    td_client.create_limit_order(clientOid=oId, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop=stop, stopPrice=stop_price, stopPriceType='MP', price=0, lever=0, size=pos["currentQty"])
    disco_log('Stoploss', msg)

def check_trailing_stop(pos: dict):
    """ Make sure the trailing stop is correct, if not, cancel and resubmit. """
    direction = get_direction(pos)
    trail_price = get_trailing_stop_price(pos)
    for item in stops['items']:
        if direction == 'long' and item['symbol'] == pos['symbol'] and item['stop'] == 'down':
            if float(item['stopPrice']) < trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                td_client.cancel_order(orderId=item['id'])
                time.sleep(.1) # Rate limit
                add_trailing_stop(pos)
        elif direction == 'short' and item['symbol'] == pos['symbol'] and item['stop'] == 'up':
            if float(item['stopPrice']) > trail_price and (item['clientOid'] == f'{pos["symbol"]}trail' or f'{pos["symbol"]}far'):
                td_client.cancel_order(orderId=item['id'])
                time.sleep(.1) # Rate limit
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
    msg = f'> [{datetime.now().strftime(strftime)}] Submitting TRAILING STOP order for {pos["symbol"]} {leverage} X {direction} position: {pos["currentQty"]} contracts @ {trail_price}'
    print(msg)
    # Lever can be 0 because stop has a value. closeOrder=True ensures a position won't be entered or increase. 'MP' means mark price, 'TP' means last traded price, 'IP' means index price
    # If using a limit order, 'price' needs a value
    td_client.create_limit_order(clientOid=oid, closeOrder=True, type='market', side=side, symbol=pos['symbol'], stop=stop, stopPrice=trail_price, stopPriceType='MP', price=trail_price, lever=0, size=amount)
    disco_log('Trailing Stop', msg)
    time.sleep(.1) # Rate limit

# Debugging
""" print(f"Positions: -------\\\n{get_positions()}")
print(f"Stops: -------\\\n{get_stops()}")
print(f"Symbols: -------\\\n{get_symbol_list()}") """

def main():
    """ Happy Trading! """
    while True:
        # Try/Except to prevent script from stopping if 'Too Many Requests' or other exception returned from Kucoin
        # TODO: [KFAS-5] Figure out which requests are trigging the rate limit
        try:

            if not initialized:
                init()
                print(f'> [{datetime.now().strftime(strftime)}] Stops will begin trailing at break-even plus {start_trailing_pcnt_lead * 1e2}% with a leeway of {leeway_pcnt * 1e2}% and increase every {trailing_bump_pcnt * 1e2}%')
                balance = round(get_futures_balance(), 2)
                print(f'> [{datetime.now().strftime(strftime)}] Account Balance: {balance} USDT -> {round(trade_pcnt * 1e2)}% of Account Balance: {round(balance * trade_pcnt, 2)} USDT')

            get_positions()
            time.sleep(.34) # Rate limit
            get_stops()
            time.sleep(.1) # Rate limit
            get_symbol_list()
            get_stop_symbol_list()

            if stops is not None:
                cancel_stops_without_pos()
                time.sleep(.34) # Rate limit

            if not positions:
                print(f"> [{datetime.now().strftime(strftime)}] No active positions... Start a trade!                              ", end="\r")
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
                # TODO: [KFAS-17] Figure out a better way to display all the data to the console
                # This doesn't work when there are multiple positions
                # The extra spaces are to make sure there is no remaining text after using end='\r'
                if len(symbols) == 1:
                    print(f'> [{datetime.now().strftime(strftime)}] Active positions:',
                        ''.join(str(get_leverage(pos)).upper() for pos in positions), 'X', ' '.join(str(pos['symbol']) for pos in positions),
                        ''.join(str(get_direction(pos)).upper() for pos in positions), ' '.join(str(pos['markPrice']) for pos in positions), '$',
                        ''.join(str(pos['currentQty']) for pos in positions), '@', ''.join(str(round(pos['unrealisedRoePcnt'] * 100, 2)) for pos in positions),
                        '%                                              ', end='\r')
                else:
                    print(f'> [{datetime.now().strftime(strftime)}] Active positions: {symbols}                           ', end='\r')

            time.sleep(sleep_time)

        except KeyboardInterrupt:
            if stops is not None:
                cancel_stops_without_pos()
            end_balance = get_futures_balance()
            session_pnl = round(end_balance - balance, 2)
            quote = requests.get("https://zenquotes.io/api/random").json()[0]["q"]
            if session_pnl >= 0:
                print('\n', quote, "Nice trades! See you tomorrow...                                            ")
            else:
                print('\n', quote, "Those sure were some trades! See you tomorrow...                            ")
            quit()

        except Exception as e:
            print(e)
            time.sleep(sleep_time)
            pass

if __name__ == '__main__':
    main()
