"""
Kucoin Futures automatic stops, trailing-stops, take-profits, and algo-trading
"""
from kucoin_futures.client import TradeData, MarketData
import time
import configparser
import requests
import pyfiglet

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

# TODO: Argument parser

""" Options """
# Number of seconds between each loop
loop_wait = 3

# Number of ticks away from liquidation price for stop price. Must be integer >= 1.
ticks_from_liq = 2

# Enable take profit orders at the profit_target_pcnt
take_profit = True

# Unrealized ROE percent target
profit_target_pcnt = 0.50

# Enable trailing stoplosses
trailing = True

# Unrealized ROE percent to start trailing at
start_trailing_pcnt = .15

# The unrealised ROE percentage for the first trailing stop
# Use a value lower than start_trailing_pcnt or the trade will be stopped out right away,
# but higher than your realized loss percent due to fees or it will close at a loss
# # TODO: Calculate what this should be based on initial leverage so that it is always enough to
# It would need to be > realized PnL * 2 to break even
trailing_pcnt = .05

# Increase in unrealized ROE percent required to bump trailing stop
trailing_count_pcnt = .05

# TODO: Some reason to keep trade opened maybe?
#leading_profit = False

# Set to True after installing SurrealDB: https://surrealdb.com/
database = True
if database:
    from surreal_db import *

# Set to true after defining a strategy and setting up SurrealDB
strategy = False
if strategy:
    from strategy import *

""" Variables """
positions = td_client.get_all_position()
stops = td_client.get_open_stop_order()
symbols = []
pos_data = {}
symbols_dict = {}
# We have to keep track of how many times the stop has been increased to know
# if we should increase it again. Multiplied with profit_pcnt
trailing_stops = {}
initialized = False

""" Functions """
def init() -> None:
    """ Get data from surrealDB """
    global symbols_dict, initialized
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'alphabet', 'GREEN')
    print("\033[91m{}\033[00m" .format('By Duplonicus\n'))
    if database:
        print("> Retreiving data from symbol table...")
        try:
            table = event_loop.run_until_complete(select_all("symbol"))
        except Exception as e:
            initialized = True
            print(e)
            print("> Install SurrealDB!")
            return
        if table == []: # If empty or doesn't exist
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
    elif positions == {'code': '200000', 'data': []}:
        positions = False
        return

def get_stops() -> dict:
    """ Returns a dictionary of active stop orders. """
    global stops
    stops = td_client.get_open_stop_order()
    return stops

def get_symbol_list() -> list:
    """ Returns a list of symbols from positions. """
    global symbols, pos_data
    symbols = []
    if not positions:
        pos_data.clear()
        return symbols
    for i, position in enumerate(positions): # Have to enumerate because it's a list?
        symbols.append(positions[i]["symbol"])
    return symbols

def get_position_data() -> dict:
    """ Checks if positions have stops and returns organized data in pos_data dict. """

    if not positions:
        print(f"> No active positions... Start a trade!", end="\r")
        return

    global pos_data, symbols_dict
    for position in positions:
        stop_loss, take_profit = False, False
        stop_price, profit_price = None, None

        # If posCost is > 0 the trade direction is long. If direction is 'long', stop is 'down' and vise-versa
        direction = "long" if position["posCost"] > 0 else "short"
        if direction == "short":
            for item in stops["items"]:
                if item["symbol"] == position["symbol"] and item["stop"] == "up":
                    stop_loss = True
                    stop_price = item["stopPrice"]
                if item["symbol"] == position["symbol"] and item["stop"] == "down":
                    take_profit = True
                    profit_price = item["stopPrice"]
        elif direction == "long":
            for item in stops["items"]:
                if item["symbol"] == position["symbol"] and item["stop"] == "down":
                    stop_loss = True
                    stop_price = item["stopPrice"]
                if item["symbol"] == position["symbol"] and item["stop"] == "up":
                    take_profit = True
                    profit_price = item["stopPrice"]
        # Get and store symbol contract details
        if position["symbol"] not in symbols_dict:
            symbol_data = md_client.get_contract_detail(position["symbol"])
            tick_size = symbol_data["tickSize"]
            symbols_dict[position["symbol"]] = symbol_data
            if database:
                try:
                    # Add or update symbol data to symbol table in DB
                    event_loop.run_until_complete(upsert_one("symbol", position["symbol"], {position["symbol"]:symbol_data}))
                except Exception as e:
                    print(e)
        else:
            symbol_data = symbols_dict[position["symbol"]]
            tick_size = float(symbol_data["tickSize"])
        unrealised_roe_pcnt = position["unrealisedRoePcnt"]
        initial_leverage = round(position['realLeverage'] * (1 + position['unrealisedRoePcnt'])) # Example: TODO add example
        # Build pos_data dictionary to make working with the data easier
        pos_data[position["symbol"]] = {"direction":direction, "liq_price":position["liquidationPrice"], "stop_loss":stop_loss, "stop_price":stop_price, "take_profit":take_profit, "profit_price":profit_price, "tick_size":tick_size, "amount":position["currentQty"], "mark_price":position["markPrice"], "initial_leverage":initial_leverage, "unrealised_roe_pcnt":unrealised_roe_pcnt }
    return pos_data

def round_to_tick_size(number: float | int, tick_size: float | int) -> float | int:
    """ Makes sure Python doesn't return a super long float for the stop order price. """
    tick_size = "{:f}".format(tick_size) # Convert to decimal float if tick_size was returned in scientific notation
    after_decimal = len(str(tick_size).split(".")[1]) # Number of digits after the decimal for tick_size
    return round(number, after_decimal)

def get_new_profit_price(direction: str, mark_price: float | int, initial_leverage: int, profit_target: float | int, tick_size: float | int) -> float | int:
    """ Returns a new take profit price.
    Calculation: mark_price + (mark_price * (profit_target / initial_leverage))
    Example: 100 + (100 * (1 / 100)) = 101 """

    if direction == "long":
        return round_to_tick_size(mark_price + (mark_price * (profit_target / initial_leverage)), tick_size)
    elif direction == "short":
        return round_to_tick_size(mark_price - (mark_price * (profit_target / initial_leverage)), tick_size)

def add_take_profits() -> None:
    """ Submits take-profit orders if not present and take_profit is True """
    if take_profit is True:
        for pos in pos_data:
            if pos_data[pos]["take_profit"] is False:
                profit_price = get_new_profit_price(pos_data[pos]["direction"], pos_data[pos]["mark_price"], pos_data[pos]["initial_leverage"], profit_target_pcnt, pos_data[pos]["tick_size"])
                # Make sure amount is a positive number as required by Kucoin
                if pos_data[pos]["amount"] > 0:
                    amount = pos_data[pos]["amount"]
                elif pos_data[pos]["amount"] < 0:
                    amount = pos_data[pos]["amount"] * -1
                print(f'> Submitting TAKE PROFIT order for {pos_data[pos]["initial_leverage"]} X {pos} {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {profit_price}')
                # Take profit orders
                if pos_data[pos]["direction"] == "long":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='up', stopPrice=profit_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
                elif pos_data[pos]["direction"] == "short":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='down', stopPrice=profit_price, stopPriceType='TP', price=0, lever=0, size=amount)

def get_new_stop_price(direction: str, liq_price: float, tick_size: float) -> float:
    """ Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price. """
    if direction == "long":
        return round_to_tick_size(liq_price + tick_size * ticks_from_liq, tick_size)
    elif direction == "short":
        return round_to_tick_size(liq_price - tick_size * ticks_from_liq, tick_size)

def get_new_trailing_price(direction: str, mark_price: float, initial_leverage: int | float, trailing_pcnt: float, tick_size: float, trailing_count: int) -> float:
    """ Returns a new trailing stop price.

        Perameters
        -----------
        trailing_count must be an integer >= 1.

        Calculation
        -----------
        1 +/- mark_price * ((trailing_pcnt * trailing_count) / leverage)

        Example
        -------
        1 + (100 * (0.1 * 1 / 100)) = 100.1 """

    if direction == "long":
        return round_to_tick_size(1 + mark_price * ((trailing_pcnt * trailing_count) / initial_leverage), tick_size)
    elif direction == "short":
        return round_to_tick_size(1 - mark_price * ((trailing_pcnt * trailing_count) / initial_leverage), tick_size) # This is correct now

def add_stops() -> None:
    """ Submits stop orders if not present. """
    for pos in pos_data:
        if pos_data[pos]["stop_loss"] is False:
            if pos_data[pos]["amount"] > 0:
                amount = pos_data[pos]["amount"]
            elif pos_data[pos]["amount"] < 0:
                amount = pos_data[pos]["amount"] * -1 # Make sure amount is a positive number as required by Kucoin
            stop_price = get_new_stop_price(pos_data[pos]["direction"], pos_data[pos]["liq_price"], pos_data[pos]["tick_size"])
            print(f'> Submitting STOP order for {pos} {pos_data[pos]["initial_leverage"]} X {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {stop_price}')
            # Submit the stoploss order
            if pos_data[pos]["direction"] == "long":
                td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
            elif pos_data[pos]["direction"] == "short":
                td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)

def check_stops() -> None:
    """ Cancels stops if no matching positions.
        Cancels stops if position size or liquidation price changes then calls add_stops(). """

    """ Cases """
    #Check passed
    command = "check_passed"

    # No stops
    if stops == {'currentPage': 1, 'pageSize': 50, 'totalNum': 0, 'totalPage': 0, 'items': []}: # No stops
        command = "no_stops"

    # Stop has no position
    for item in stops["items"]:
        if item["symbol"] not in symbols:
            command = "stop_without_position"

    # Position amount changed
    for pos in pos_data.items():
        for item in stops["items"]:
            if item["symbol"] == pos[0]:
            # Kucoin returns a positive number for item["size"], make sure ours is too
                if pos[1]["amount"] > 0:
                    amount = pos[1]["amount"]
                elif pos[1]["amount"] < 0:
                    amount = pos[1]["amount"] * -1
                # Check if position amount doesn't match stop up or down amount
                if item["symbol"] == pos[0] and item["size"] != amount:
                    command = "stop_amount"

    # Liquidation price changed - I think this is the only case that could potentially be a duplicate
    # This should get called if the margin changes but the amount does not
    if command != "stop_amount":
        for pos in pos_data.items():
                if pos[1]['direction'] == 'long':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "down":
                            new_stop_price = get_new_stop_price(pos[1]["direction"], pos[1]["liq_price"], pos[1]["tick_size"])
                            if item["symbol"] == pos[0] and float(item["stopPrice"]) != new_stop_price:
                                print(f'> Liquidation price changed for {pos[1]["initial_leverage"]} X {item["symbol"]}! Resubmitting stop {item["stop"].upper()} order...')
                                command = "liquidation_price"
                elif pos[1]['direction'] == 'short':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "up":
                            new_stop_price = get_new_stop_price(pos[1]["direction"], pos[1]["liq_price"], pos[1]["tick_size"])
                            if item["symbol"] == pos[0] and float(item["stopPrice"]) != new_stop_price:
                                print(f'> Liquidation price changed for {pos[1]["initial_leverage"]} X {item["symbol"]}! Resubmitting stop {item["stop"].upper()} order...')
                                command = "liquidation_price"

    # Trailing stop ready to be bumped - comes befor start_trailing so we know if not to run start_trailing
    if False:
        command = "bump_stop"

    # Unrealised ROE high enough to start trailing
    if command != 'bump_stop':
        for pos in pos_data.items():
                if pos[1]['direction'] == 'long':
                    for item in stops["items"]:
                        if item["symbol"] == pos[0] and float(pos[1]["unrealised_roe_pcnt"]) > start_trailing_pcnt:
                            print(f'> {pos[1]["initial_leverage"]} X {item["symbol"]} {pos[1]["direction"]} position @ {round(pos[1]["unrealised_roe_pcnt"] * 100, 2)}% profit is ready for TRAILING STOP!')
                            command = "start_trailing"
                elif pos[1]['direction'] == 'short':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "up":
                            new_stop_price = get_new_stop_price(pos[1]["direction"], pos[1]["liq_price"], pos[1]["tick_size"])
                            if item["symbol"] == pos[0] and float(pos[1]["unrealised_roe_pcnt"]) > start_trailing_pcnt:
                                print(f'> {pos[1]["initial_leverage"]} X {item["symbol"]} {pos[1]["direction"]} position @ {round(pos[1]["unrealised_roe_pcnt"] * 100, 2)}% profit and is ready for TRAILING STOP!')
                                command = "start_trailing"

    """ Matches """
    match command:
        # No stops
        case 'no_stops':
            return

        # Stop has no position
        case 'stop_without_position':
            for item in stops["items"]:
                if item["symbol"] not in symbols:
                    print(f'> No position for {item["symbol"]}! Cancelling STOP {item["stop"].upper()} orders...')
            td_client.cancel_all_stop_order(item["symbol"])
            add_stops()
            return

        # Position amount changed
        case 'stop_amount':
            for pos in pos_data.items():
                if pos[1]['direction'] == 'long':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "down":
                            print(f'> Position size changed for {item["symbol"]}! Resubmitting stop {item["stop"].upper()} order...')
                elif pos[1]['direction'] == 'short':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "up":
                            print(f'> Position size changed for {item["symbol"]}! Resubmitting stop {item["stop"].upper()} order...')
            td_client.cancel_all_stop_order(item["symbol"])
            add_stops()
            return

        # Liquidation price changed
        case 'liquidation_price':
            td_client.cancel_all_stop_order(item["symbol"])
            add_stops()
            return

        # Trailing stop ready to be bumped
        case 'bump_trailing':
            return

        # Unrealised ROE high enough to start trailing
        case 'start_trailing':

            for pos in pos_data.items():
                if pos[1]['direction'] == 'long':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "down":
                            add_trailing(item['symbol'], pos[1]['direction'], item['size'], pos[1]['mark_price'], pos[1]['initial_leverage'], trailing_pcnt, pos[1]['tick_size'], 1)
                            #trailing_stops[item["symbol"]] = {"symbol":item["symbol"], "count":1}
                            print('test')
                elif pos[1]['direction'] == 'short':
                    for item in stops["items"]:
                        if item['symbol'] == pos[0] and item["stop"] == "up":
                            add_trailing(item['symbol'], pos[1]['direction'], item['size'], pos[1]['mark_price'], pos[1]['initial_leverage'], trailing_pcnt, pos[1]['tick_size'], 1)
                            #trailing_stops[item["symbol"]] = {"symbol":item["symbol"], "count":1}
            return

        # Trailing stop ready to be bumped
        case 'bump_stop':
            # cancel stops
            # add stops or new function?
            return

        # Check passed
        case 'check_passed':
            return

def add_trailing(symbol, direction: str, amount: int, mark_price: float, initial_leverage: float, trailing_pcnt: float, tick_size: float, trailing_count: int) -> None :
    """ Submits strailing stop """
    stop_price = get_new_trailing_price(direction, mark_price, initial_leverage, trailing_pcnt, tick_size, trailing_count)
    if amount < 0:
        amount = amount * -1 # Make sure amount is a positive number as required by Kucoin
    td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=symbol, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
    #print(f'trailing stops: {trailing_stops}')
    #trailing_stops[symbol]['count'] = trailing_stops[symbol]['count'] + 1

def buy():
    if check_long_condition() is True:
        # Add code for what to do if your buy condition is True
        pass

def sell():
    if check_short_condition() is True:
        # Add code for what to do if your sell condition is True
        pass

# Debugging - This will break the script if there are no positions. Comment out if so.
try:
    print(f"Positions: -------\\\n{positions}")
    print(f"Stops: -------\\\n{stops}")
    print(f"Symbols: -------\\\n{get_symbol_list()}")
    print(f"Pos Data: -------\\\n{get_position_data()}")
except:
    print("You Fool!")

def main():
    """ Take from the market maker """
    while True:
        # Try/Except to prevent script from stopping if 'Too Many Requests' or other exception returned from Kucoin
        # TODO: Figure out which requests are too close together though it doesn't really matter because the script will finish what it wants to do after the timeout
        try:
            if not initialized:
                init()
            get_positions()
            get_stops()
            get_symbol_list()
            get_position_data()
            add_take_profits()
            check_stops()
            add_stops()
            if strategy and long:
                buy()
            if strategy and short:
                sell()

            # Display active positions
            if positions:
                print('> Active positions:', ', '.join(str(symbol) for symbol in symbols), end='\r')

            time.sleep(loop_wait)

        except KeyboardInterrupt:
            quote = requests.get("https://zenquotes.io/api/random")
            print(quote.json()[0]["q"], "Nice trades!!! See you tomorrow... :)")
            quit()

        """ except Exception as e:
            print(e)
            pass """

if __name__ == '__main__':
    main()
