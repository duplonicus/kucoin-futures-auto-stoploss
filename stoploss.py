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
pos_data = {}
loop_wait = 5

# Get positions, stops, and take profits
positions = td_client.get_all_position()
stops = td_client.get_open_stop_order()

# Functions
# Returns a list of symbols for active trades
def get_symbol_list():
    symbols = []
    i = 0
    if positions == {'code': '200000', 'data': []}:
        return symbols
    for position in positions:
        symbols.append(positions[i]["symbol"])
        i += 1
    return symbols

# Check if positions have stops and get some data
def get_position_data():
    for position in positions:
        stop_loss, take_profit = False, False
        stop_price, profit_price = None, None
        # If direction is 'long', stop is 'down' and vise-versa
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

# Returns a value one tick size away from the liquidation price
def get_new_stop_price(direction, liq_price, tick_size):
    if direction == "long":
        return liq_price + tick_size
    elif direction == "short":
        return liq_price - tick_size

# Submit stop orders if not present
def add_stops():   
    for pos in pos_data:
        if pos_data[pos]["stop_loss"] == False:
            stop_price = get_new_stop_price(pos_data[pos]["direction"], pos_data[pos]["liq_price"], pos_data[pos]["tick_size"])
            # Make sure amount is a positive number
            if pos_data[pos]["amount"] > 0:
                amount = pos_data[pos]["amount"]
            elif pos_data[pos]["amount"] < 0:
                amount = pos_data[pos]["amount"] * -1 
            print(f'Submitting STOP order for {pos} {pos_data[pos]["direction"]} position @ {stop_price}')
            # Stop orders
            if pos_data[pos]["direction"] == "long":
                td_client.create_limit_order(reduceOnly=True, closeOrder=False, type='market', side='sell', symbol=pos, stop='down', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)
            elif pos_data[pos]["direction"] == "short":
                td_client.create_limit_order(reduceOnly=True, closeOrder=False, type='market', side='buy', symbol=pos, stop='up', stopPrice=stop_price, stopPriceType='TP', price=0, lever=0, size=amount)

# Cancel stops with no positions
def check_stops():
    for item in stops["items"]:
        if item["symbol"] not in get_symbol_list():
            # cancel stop order here
            td_client.cancel_all_stop_order(item["symbol"])

def main():
    while True:

        global positions, stops

        # Get positions
        positions = td_client.get_all_position()   
        if positions == {'code': '200000', 'data': []}:
            print("No active positions... Start a trade!")
            check_stops()
            time.sleep(loop_wait)
            continue 

        # Get stop and take profit orders
        stops = td_client.get_open_stop_order()

        # Organize data and print to console
        print(f"Positions: {get_symbol_list()}\n\nPositions Data:\n{get_position_data()}\n")

        # Submit stop orders
        add_stops()

        # Cancel stop orders if no matching position
        check_stops()

        # Wait for 5 seconds
        time.sleep(loop_wait)

if __name__ == '__main__':
    main()
