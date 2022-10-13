from kucoin_futures.client import TradeData, MarketData
import time
import configparser

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

# Connection info
api_key = config['api']['key']
api_secret = config['api']['secret']
api_passphrase = config['api']['passphrase']

# Rest API Wrapper Client Objects
td_client = TradeData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')
md_client = MarketData(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url='https://api-futures.kucoin.com')

# Variables
positions = td_client.get_all_position()
stops = td_client.get_open_stop_order()
symbols = []
pos_data = {}
loop_wait = 3
ticks_from_liq = 2 # Number of ticks away from liquidation price for stop price. Must be integer >= 1.

# Functions
# Returns a dictionary containing Kucoin response
def get_positions():
    global positions
    positions = td_client.get_all_position()
    return positions

# Returns a dictionary containing Kucoin response
def get_stops():
    global stops
    stops = td_client.get_open_stop_order()
    return stops

# Returns a list of symbols for active trades
def get_symbol_list():    
    global symbols
    symbols = []
    if positions == {'code': '200000', 'data': []}: # No positions
        return symbols
    for count, position in enumerate(positions):
        symbols.append(positions[count]["symbol"])
    return symbols

# Check if positions have stops and get some data
def get_position_data():
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
        amount = position["currentQty"]
        symbol = md_client.get_contract_detail(position["symbol"])
        pos_data[position["symbol"]] = {"direction":direction, "liq_price":position["liquidationPrice"], "stop_loss":stop_loss, "stop_price":stop_price, "take_profit":take_profit, "profit_price":profit_price, "tick_size":symbol["tickSize"], "amount":amount }
    return pos_data

# Returns a stop price (tick_size * ticks_from_liq) away from the liquidation price
def get_new_stop_price(direction, liq_price, tick_size):
    if direction == "long":
        return round_to_tick_size(liq_price + tick_size * ticks_from_liq, tick_size)
    elif direction == "short":
        return round_to_tick_size(liq_price - tick_size * ticks_from_liq, tick_size)

# Make sure Python doesn't return a super long float for the stop order price
def round_to_tick_size(number, tick_size):
    tick_size = "{:f}".format(tick_size) # Convert to decimal float if tick_size was returned in scientific notation
    after_decimal = len(str(tick_size).split(".")[1]) # Number of digits after the decimal for tick_size
    return round(number, after_decimal)

# Submit stop orders if not present
def add_stops():
    for pos in pos_data:
        if pos_data[pos]["stop_loss"] is False:
            stop_price = get_new_stop_price(pos_data[pos]["direction"], pos_data[pos]["liq_price"], pos_data[pos]["tick_size"])
            # Make sure amount is a positive number as required by Kucoin
            if pos_data[pos]["amount"] > 0:
                amount = pos_data[pos]["amount"]
            elif pos_data[pos]["amount"] < 0:
                amount = pos_data[pos]["amount"] * -1
            print(f'> Submitting STOP order for {pos} {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {stop_price}')
            # Stop orders
            if pos_data[pos]["direction"] == "long":
                td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
            elif pos_data[pos]["direction"] == "short":
                td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)

# Submit take-profit orders if not present and take_profit is True
# WIP ########
def add_take_profit():
    for pos in pos_data:
        if pos_data[pos]["stop_loss"] is False:
            stop_price = get_new_stop_price(pos_data[pos]["direction"], pos_data[pos]["liq_price"], pos_data[pos]["tick_size"])
            # Make sure amount is a positive number as required by Kucoin
            if pos_data[pos]["amount"] > 0:
                amount = pos_data[pos]["amount"]
            elif pos_data[pos]["amount"] < 0:
                amount = pos_data[pos]["amount"] * -1
            print(f'> Submitting STOP order for {pos} {pos_data[pos]["direction"]} position: {pos_data[pos]["amount"] * -1} contracts @ {stop_price}')
            # Stop orders
            if pos_data[pos]["direction"] == "long":
                td_client.create_limit_order(reduceOnly=True, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount) # size and lever can be 0 because stop has a value. reduceOnly=True ensures a position won't be entered or increase. 'TP' means last traded price
            elif pos_data[pos]["direction"] == "short":
                td_client.create_limit_order(reduceOnly=True, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)

# Cancel stops with no matching positions and redo stops if position size or liquidation price changes
def check_stops():    
    # Check if no stops and return
    if stops == {'currentPage': 1, 'pageSize': 50, 'totalNum': 0, 'totalPage': 0, 'items': []}: # No stops
        return

    # Cancel stops if no matching position
    for item in stops["items"]:
        if item["symbol"] not in symbols:            
            print(f'> No position for {item["symbol"]}! Cancelling STOP orders...')
            td_client.cancel_all_stop_order(item["symbol"])
            # check_stops() should only get this far if called before add_stops()

        # Should this be split into two function here?

        # Redo stops if position amount changes
        for pos in pos_data.items(): # Each item is a tuple containing a string and dictionary: ('symbol', {direction:, liq_price:, ...})
            new_stop_price = str(get_new_stop_price(pos[1]["direction"], pos[1]["liq_price"], pos[1]["tick_size"]))
            # Kucoin returns a positive number for item["size"], make sure ours is too
            if pos[1]["amount"] > 0:
                amount = pos[1]["amount"] 
            elif pos[1]["amount"] < 0:
                amount = pos[1]["amount"] * -1
            # Check if position amount doesn't match stop amount
            if item["symbol"] == pos[0] and item["size"] != amount:
                print(f'> Position size changed for {item["symbol"]}! Resubmitting stop order...')
                td_client.cancel_all_stop_order(item["symbol"])
                add_stops()

            # Redo stops if stop price doesn't match position liquidation price. Don't compare to take profit price
            if item["symbol"] == pos[0] and item["stopPrice"] != new_stop_price:
                if item["stop"] == "down" and pos[1]["direction"] == "long": # Take profit of long
                    continue
                elif item["stop"] == "up" and pos[1]["direction"] == "short": # Take profit of short
                    continue
                elif item["stop"] == "down" and pos[1]["direction"] == "long" or item["stop"] == "up" and pos[1]["direction"] == "short": # The stops you are looking for
                    print(f'> Liquidation price changed for {item["symbol"]}! Resubmitting stop order...')
                    td_client.cancel_all_stop_order(item["symbol"])
                    add_stops()

# Debugging
print(f"Positions: -------\\\n{positions}")
print(f"Stops: -------\\\n{stops}")
print(f"Symbols: -------\\\n{get_symbol_list()}")
print(f"Pos Data: -------\\\n{get_position_data()}")

def main():        
    while True:

        # Try/Except to prevent script from stopping if 'Too Many Requests' response returned from Kucoin
        try:
            # Get positions, stops, and take profits (also stops)
            get_positions()            
            get_stops()
            # Get symbol list from positions
            get_symbol_list()

            # Continue looping if no positions
            if positions == {'code': '200000', 'data': []}: # No positions
                # In case a position was just cosed, run check_stops() to close any extra stops
                check_stops()
                print(f"> No active positions... Start a trade!", end="\r")             
                time.sleep(loop_wait)
                continue

            # Get positions symbol list and data
            
            get_position_data()  

            # Submit stop orders
            add_stops()

            # Cancel stop orders if no matching position
            check_stops()

            print(f"> Active positions: {symbols}", end="\r")

            # Wait for loop_wait seconds
            time.sleep(loop_wait)

        except Exception as e:
            print(e)
            pass

if __name__ == '__main__':
    main()
