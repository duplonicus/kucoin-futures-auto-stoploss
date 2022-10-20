""" Example data """

# Positions: -------\
[{
    'id': '622582d923c84b0001e3f98e', 'symbol': 'ETHUSDTM', 'autoDeposit': False, 'maintMarginReq': 0.007, 'riskLimit': 200000, 'realLeverage': 97.08, 'crossMode': False, 'delevPercentage': 0.27, 'openingTimestamp': 1666233982294, 'currentTimestamp': 1666240944620, 'currentQty': -2, 'currentCost': -25.6615, 'currentComm': 0.01667721, 'unrealisedCost': -25.6615, 'realisedGrossCost': 0.0, 'realisedCost': 0.01667721, 'isOpen': True, 'markPrice': 1287.03, 'markValue': -25.7406, 'posCost': -25.6615, 'posCross': 0.00127954, 'posInit': 0.34215333, 'posComm': 0.01560296, 'posLoss': 0.0, 'posMargin': 0.35903583, 'posMaint': 0.19523346, 'maintMargin': 0.27993583, 'realisedGrossPnl': 0.0, 'realisedPnl': -0.01411659, 'unrealisedPnl': -0.0791, 'unrealisedPnlPcnt': -0.0031, 'unrealisedRoePcnt': -0.2312, 'avgEntryPrice': 1283.08, 'liquidationPrice': 1291.25, 'bankruptPrice': 1300.25, 'settleCurrency': 'USDT', 'isInverse': False, 'maintainMargin': 0.007
}]

# Stops: -------\
{

    'currentPage': 1,
    'pageSize': 50,
    'totalNum': 4,
    'totalPage': 1,
    'items': [{
        # This is a stop manually entered from the Positions tab, we can tell the difference because 'timeInForce' == '' and 'clientOId' == None and 'reduceOnly' == False
        'id': '6350d1a3ebeed60001014626', 'symbol': 'ETHUSDTM', 'type': 'market', 'side': 'buy', 'price': None, 'size': 2, 'value': '0', 'dealValue': '0', 'dealSize': 0, 'stp': '', 'stop': 'up', 'stopPriceType': 'TP', 'stopTriggered': None, 'stopPrice': '1291.1', 'timeInForce': '', 'postOnly': False, 'hidden': False, 'iceberg': False, 'leverage': '1', 'forceHold': False, 'closeOrder': True, 'visibleSize': None, 'clientOid': None, 'remark': None, 'tags': None, 'isActive': True, 'cancelExist': False, 'createdAt': 1666240931000, 'updatedAt': 1666240931000, 'endAt': None, 'orderTime': None, 'settleCurrency': 'USDT', 'status': 'open', 'filledSize': 0, 'filledValue': '0', 'reduceOnly': False
    }

    ,
        # This is a stop manually entered from the Positions tab, we can tell the difference because 'timeInForce' == '' and 'clientOId' == None and 'reduceOnly' == False
        {
        'id': '6350d1a3ebeed60001014631', 'symbol': 'ETHUSDTM', 'type': 'market', 'side': 'buy', 'price': None, 'size': 2, 'value': '0', 'dealValue': '0', 'dealSize': 0, 'stp': '', 'stop': 'down', 'stopPriceType': 'TP', 'stopTriggered': None, 'stopPrice': '1270.2', 'timeInForce': '', 'postOnly': False, 'hidden': False, 'iceberg': False, 'leverage': '1', 'forceHold': False, 'closeOrder': True, 'visibleSize': None, 'clientOid': None, 'remark': None, 'tags': None, 'isActive': True, 'cancelExist': False, 'createdAt': 1666240931000, 'updatedAt': 1666240931000, 'endAt': None, 'orderTime': None, 'settleCurrency': 'USDT', 'status': 'open', 'filledSize': 0, 'filledValue': '0', 'reduceOnly': False
    }

    ,
        {
        'id': '6350d1872096610001457f2e', 'symbol': 'ETHUSDTM', 'type': 'market', 'side': 'buy', 'price': '0', 'size': 2, 'value': '0', 'dealValue': '0', 'dealSize': 0, 'stp': '', 'stop': 'up', 'stopPriceType': 'TP', 'stopTriggered': None, 'stopPrice': '1291.15', 'timeInForce': 'GTC', 'postOnly': False, 'hidden': False, 'iceberg': False, 'leverage': '1', 'forceHold': False, 'closeOrder': False, 'visibleSize': None, 'clientOid': '7f33a1a9503111edaa886245b5038bc7', 'remark': None, 'tags': None, 'isActive': True, 'cancelExist': False, 'createdAt': 1666240903000, 'updatedAt': 1666240903000, 'endAt': None, 'orderTime': None, 'settleCurrency': 'USDT', 'status': 'open', 'filledSize': 0, 'filledValue': '0', 'reduceOnly': True
    }

    ,
        {
        'id': '6350d17f7dcb7f000162b828', 'symbol': 'ETHUSDTM', 'type': 'market', 'side': 'buy', 'price': '0', 'size': 2, 'value': '0', 'dealValue': '0', 'dealSize': 0, 'stp': '', 'stop': 'down', 'stopPriceType': 'TP', 'stopTriggered': None, 'stopPrice': '1278.3604', 'timeInForce': 'GTC', 'postOnly': False, 'hidden': False, 'iceberg': False, 'leverage': '1', 'forceHold': False, 'closeOrder': False, 'visibleSize': None, 'clientOid': '7ab5f77f503111ed833f6245b5038bc7', 'remark': None, 'tags': None, 'isActive': True, 'cancelExist': False, 'createdAt': 1666240895000, 'updatedAt': 1666240895000, 'endAt': None, 'orderTime': None, 'settleCurrency': 'USDT', 'status': 'open', 'filledSize': 0, 'filledValue': '0', 'reduceOnly': True
    }]
}

# Symbols: -------\
['ETHUSDTM']

# Pos Data: -------\
{
    'ETHUSDTM': {
        'direction': 'short', 'liq_price': 1291.25, 'stop_loss': True, 'stop_price': '1291.15', 'take_profit': True, 'profit_price': '1278.3604', 'tick_size': 0.05, 'amount': -2, 'mark_price': 1287.03, 'initial_leverage': 75, 'unrealised_roe_pcnt': -0.2312
    }
}

# K Lines
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