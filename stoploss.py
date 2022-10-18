"""
Kucoin Futures automatic stops, trailing stops, take profits, and algo-trading
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

# Options
loop_wait = 3 # Number of seconds between each loop
ticks_from_liq = 2 # Number of ticks away from liquidation price for stop price. Must be integer >= 1.
take_profit = True # Set to True to enable take profit orders at the profit_target_pcnt
profit_target_pcnt = 0.6 # Unrealized ROE percent target
trailing = True # Set to True to enable trailing stoplosses
start_trailing_pcnt = .2 # Unrealized ROE percent to start trailing at. TODO: Calculate what this should be based on initial leverage so that it is always enough to make up for fees
trailing_pcnt = .04 # Used in trailing stop calculation. Use a value lower than start_trailing_pcnt or the trade will be stopped out right away but higher than your realized loss percent due to fees or it will close at a loss
trailing_count_pcnt = .05 # Increase in unrealized ROE percent required to bump trailing stop
#leading_profit = False # TODO: Some reason to keep trade opened maybe?
database = True # Set to True after installing SurrealDB: https://surrealdb.com/
if database:
    from surreal_db import *
strategy = True # Set to true after defining a strategy and setting up SurrealDB
if strategy:
    from strategy import *

# Variables
positions = td_client.get_all_position()
stops = td_client.get_open_stop_order()
symbols = []
pos_data = {}
symbols_dict = {}
trailing_stops = {} # We have to keep track of how many times the stop has been increased to know if we should increase it again. Multiplied with profit_pcnt
initialized = False

# Functions
def init() -> None:
    """ For real? """
    global symbols_dict, initialized
    pyfiglet.print_figlet("Kucoin Futures Position Manager", 'alphabet', 'GREEN')    
    print("\033[91m{}\033[00m" .format('By Duplonicus\n'))
    if database:
        print("Retreiving data from symbol table...")
        try:
            table = event_loop.run_until_complete(select_all("symbol"))
        except Exception as e:
            initialized = True
            print(e)
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
        print("Install SurrealDB!")

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
    global pos_data, symbols_dict
    if not positions:
        print(f"> No active positions... Start a trade!", end="\r")
        pos_data = {}
        return
    
    for position in positions:
        stop_loss, take_profit = False, False
        stop_price, profit_price = None, None
        p = position["symbol"]
        # If posCost is > 0 the trade direction is long. If direction is 'long', stoploss is 'down', take-profit is 'up', and vise-versa
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
            symbol_data = symbols_dict[position["symbol"]] ###
            tick_size = float(symbol_data["tickSize"])
            pos_data[position["symbol"]] = symbol_data
            pos_data[position["symbol"]]["stop_is_trailing"] = False
        # TODO: double check the math on initial_leverage or find a different way but I think it's good because it eventually is rounded to an int. So far this is correct.
        unrealised_roe_pcnt = position['unrealisedRoePcnt']
        initial_leverage = round(position['realLeverage'] * (1 + position["unrealisedRoePcnt"])) # This is confusing but as close as I can get. Not sure if we can get this or why not.
        # Update or create pos_data dictionary to make working with the data easier
        if position["symbol"] in pos_data.keys():
            pos_data[position["symbol"]].update({"direction":direction, "liq_price":position["liquidationPrice"], "stop_loss":stop_loss, "stop_price":stop_price, "take_profit":take_profit, "profit_price":profit_price, "tick_size":tick_size, "amount":position["currentQty"], "mark_price":position["markPrice"], "initial_leverage":initial_leverage, "unrealised_roe_pcnt":unrealised_roe_pcnt})
        else:
            pos_data[position["symbol"]] = {"direction":direction, "liq_price":position["liquidationPrice"], "stop_loss":stop_loss, "stop_price":stop_price, "take_profit":take_profit, "profit_price":profit_price, "tick_size":tick_size, "amount":position["currentQty"], "mark_price":position["markPrice"], "initial_leverage":initial_leverage, "unrealised_roe_pcnt":unrealised_roe_pcnt, "stop_is_trailing":False}
        return pos_data

def round_to_tick_size(number, tick_size: float) -> float:
    """ Makes sure Python doesn't return a super long float for the stop order price. """
    tick_size = "{:f}".format(tick_size) # Convert to decimal float if tick_size was returned in scientific notation
    after_decimal = len(str(tick_size).split(".")[1]) # Number of digits after the decimal for tick_size
    return round(number, after_decimal)

def get_new_stop_price(direction: str, liq_price: float, tick_size: float) -> float:
    """ Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price. """
    if direction == "long":
        return round_to_tick_size(liq_price + tick_size * ticks_from_liq, tick_size)
    elif direction == "short":
        return round_to_tick_size(liq_price - tick_size * ticks_from_liq, tick_size)

def get_new_trailing_price(direction: str, mark_price: float, initial_leverage: float, trailing_pcnt: float, tick_size: float, trailing_count: int) -> float:
    """ Returns a new trailing stop price.

        Perameters 
        -----------
        trailing_count must be an integer >= 1.

        Calculation 
        -----------
        mark_price +/- (mark_price * ((trailing_pcnt * trailing_count) / initial_leverage))

        Example
        -------
        100 + (100 * (0.1 * 1 / 100)) = 100.1 """
    if direction == "long":
        return round_to_tick_size(mark_price + (mark_price * ((trailing_pcnt * trailing_count) / initial_leverage)), tick_size)
    elif direction == "short":
        return round_to_tick_size(mark_price - (mark_price * ((trailing_pcnt * trailing_count) / initial_leverage)), tick_size)

def add_stops() -> None:
    """ Submits stop or trailing-stop orders if not present. """
    for pos in pos_data:
        # If no stoploss
        # TODO: pos_data only has one symbol
        if pos_data[pos]["stop_loss"] is False:
            # Get the stop price TODO: Don't call both calculations
            stop_price = get_new_stop_price(pos_data[pos]["direction"], pos_data[pos]["liq_price"], pos_data[pos]["tick_size"])

            # Check if unrealized profit percentage is high enough to start trailing
            print("Pofit % > start_trailing %:", float(pos_data[pos]["unrealised_roe_pcnt"]) > start_trailing_pcnt, "unrealised_roe_pcnt", float(pos_data[pos]["unrealised_roe_pcnt"]), "start_trailing_pcnt", start_trailing_pcnt, "\n")
            if trailing and float(pos_data[pos]["unrealised_roe_pcnt"]) > start_trailing_pcnt:
                trailing_count = 1
                stop_price = get_new_trailing_price(pos_data[pos]["direction"], pos_data[pos]["mark_price"], pos_data[pos]["initial_leverage"], trailing_pcnt, pos_data[pos]["tick_size"], trailing_count)
                del pos_data[pos]["stop_is_trailing"]
                pos_data[pos]["stop_is_trailing"] = True

            # Make sure amount is a positive number as required by Kucoin
            amount = pos_data[pos]["amount"] if pos_data[pos]["amount"] > 0 else pos_data[pos]["amount"] * -1

            # Regular stop orders # WHY IS THIS RUNNING WHEN NO POSITIONS?????? -> pos_data was persisting though it shouldn't
            if pos_data[pos]["stop_is_trailing"] is False:
                print(f'> Submitting STOP order for {pos_data[pos]["initial_leverage"]} X {pos} {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {stop_price}')
                # Stop orders
                if pos_data[pos]["direction"] == "long":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because 'stop' has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price.
                elif pos_data[pos]["direction"] == "short":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)

            # Trailing stop orders
            if pos_data[pos]["stop_is_trailing"] is True:   
                print(f'> Submitting TRAILING STOP order for {pos_data[pos]["initial_leverage"]} X {pos} {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {stop_price}')             
                if pos_data[pos]["direction"] == "long":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)
                elif pos_data[pos]["direction"] == "short":
                    td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)
                
                trailing_stops.update({pos[0]:trailing_count + 1})

def get_new_profit_price(direction: str, mark_price: float, initial_leverage: float, profit_target: float, tick_size: float) -> float:
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

def check_stops() -> None:
    """ Cancels stops with no matching positions and redoes stops if position size or liquidation price changes, redoes stops if enough profit to bump trailing stop """
    # TODO: Break into seperate functions
    # Check if no stops and return
    if stops == {'currentPage': 1, 'pageSize': 50, 'totalNum': 0, 'totalPage': 0, 'items': []}: # No stops
        return
    
    # Loop through stops
    for item in stops["items"]:

        # Cancel stops if no matching position
        if item["symbol"] not in symbols:            
            print(f'> No position for {item["symbol"]}! Cancelling STOP {item["stop"].upper()} order...')
            td_client.cancel_all_stop_order(item["symbol"])
            if item["symbol"] in trailing_stops:
                del trailing_stops[item["symbol"]]
                del pos_data[pos[item["symbol"]]]
        
        # Loop through Positions
        for pos in pos_data.items(): # Each item is a tuple containing a string and dictionary: ('symbol', {direction:, liq_price:, ...}) = pos[0] = symbol, pos[1]

            # Figure out if we are going to call get_new_stop_price() or get_new_trailing_price()
            if item["symbol"] == pos[0] and (pos[1]["stop_is_trailing"] is None or pos[1]["stop_is_trailing"] is False):
                new_stop_price = str(get_new_stop_price(pos[1]["direction"], pos[1]["liq_price"], pos[1]["tick_size"]))
                pos[1]["stop_is_trailing"] = False
            # Already a trailing stop
            if trailing and item["symbol"] == pos[0] and pos[0] in trailing_stops: 
                trailing_count = trailing_stops[pos[0]]
                trailing_stops.update({pos[0]:trailing_count})
            # Not already a trailing stop        
            #print("Unrealised ROE > Start Trailing?", float(pos[1]["unrealised_roe_pcnt"]) > start_trailing_pcnt, '\n', "unrealised_roe_pcnt", float(pos[1]["unrealised_roe_pcnt"]), '\n', "start_trailing_pcnt", start_trailing_pcnt, "\n")
            if float(pos[1]["unrealised_roe_pcnt"]) > start_trailing_pcnt and pos[0] not in trailing_stops:
                trailing_stops[pos[0]] = 1
                trailing_count = trailing_stops[pos[0]]
                new_stop_price = str(get_new_trailing_price(pos[1]["direction"], pos[1]["mark_price"], pos[1]["initial_leverage"], trailing_pcnt, pos[1]["tick_size"], trailing_count))
                td_client.cancel_all_stop_order(item["symbol"])
                pos[1]["stop_is_trailing"] = True
                add_stops()
            # Check if position amount changes. Kucoin returns a positive number for item["size"], make sure ours is too
            # TODO: This isn't running
            amount = pos[1]["amount"] if pos[1]["amount"] > 0 else pos[1]["amount"] * -1
            if item["symbol"] == pos[0] and item["size"] != amount:
                print(f'> Position size changed for {item["symbol"]}! Resubmitting stop {item["stop"].upper()} order...')
                td_client.cancel_all_stop_order(item["symbol"])
                add_stops()

            # Check if time to bump trailing stop            
            if item["symbol"] == pos[0] and item["stopPrice"] < new_stop_price:
                """ if item["stop"] == "down" and pos[1]["direction"] == "long": # Take profit of long
                    break
                elif item["stop"] == "up" and pos[1]["direction"] == "short": # Take profit of short
                    break """
                if item["stop"] == "down" and pos[1]["direction"] == "long" or item["stop"] == "up" and pos[1]["direction"] == "short": # The stops you are looking for
                    print("hit me bump")
                    print(f'> Bumping trailing stop for {item["symbol"]}! Resubmitting STOP {item["stop"].upper()} order...')
                    td_client.cancel_all_stop_order(item["symbol"])
                    pos[1]["stop_is_trailing"] = True
                    """ trailing_count = trailing_stops[pos[0]] + 1
                    trailing_stops[pos[0]].update(f"{pos[0]}:{trailing_stops[pos[0]] + 1}")  """
                    add_stops()

            # Check if stop price doesn't match position liquidation price +/- ticks_from_liq. Don't compare to take profit price. Don't run if position has a trailing stop. Only run if no trailing stop.
            if item["symbol"] == pos[0] and item["stopPrice"] != new_stop_price and pos[1]["stop_is_trailing"] is False:
                if item["stop"] == "down" and pos[1]["direction"] == "long": # Take profit of long
                    continue
                elif item["stop"] == "up" and pos[1]["direction"] == "short": # Take profit of short
                    continue
                elif item["stop"] == "down" and pos[1]["direction"] == "long" or item["stop"] == "up" and pos[1]["direction"] == "short": # The stops you are looking for
                    print(f'> Liquidation price changed for {item["symbol"]}! Resubmitting STOP {item["stop"].upper()} order...')
                    td_client.cancel_all_stop_order(item["symbol"])
                    add_stops()

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
    """ print(f"Positions: -------\\\n{positions}")
    print(f"Stops: -------\\\n{stops}")
    print(f"Symbols: -------\\\n{get_symbol_list()}")
    print(f"Pos Data: -------\\\n{get_position_data()}") """
except:
    print("You Fool!")

def main():
    """ Happy Trading :) """
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
            add_stops()
            add_take_profits()
            check_stops()
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
