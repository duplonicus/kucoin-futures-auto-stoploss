# kucoin-futures-auto-stoploss

Automatic stop-losses, trailing stop-losses, take-profits, and algo-trading

___

The main purpose of this script is to prevent liquidation events. When a position exists or is entered, it creates a stoploss and take-profit order at the specified targets, resubmits the orders if the position size or liquidation price changes, or cancels the orders if the position is closed. It can also manage trailing-stops at the specified unrealized ROE percentages.

The orders appear on the Stop Orders tab and the trader can still use the stop/take-profit button on the Positions tab to set a closer stop or take profit price.

Even if the stop is only a few ticks away from the liquidation price, being stopped out is better than being liquidated because it preserves your maintenance margin. More info on this [here](https://medium.com/@Austerity_Sucks/why-you-should-never-use-your-liquidation-price-as-a-stop-loss-on-bitcoin-futures-30655f280ddd).

## Installation

___

<details>
<summary>Instructions
</summary>

1. Clone the repository:

        git clone https://github.com/duplonicus/kucoin-futures-auto-stoploss.git
2. Install [Python 3.10](https://www.python.org/downloads/release/python-3100/) or setup new virtual environment for 3.10.

3. Install the requirements from a terminal in the repository with pip.

        pip install -r requirements.txt

4. Install [SurrealDB](https://surrealdb.com/) and set respective options in stoploss.py to True to enable trade logging and algo-trading.

5. Create secret.ini in the root of the repository and add your Kucoin API connection info.

        # Example secret.ini file
        [api]
        key =
        secret =
        passphrase =

</details>

## Algo-trading

___

Define your strategy in strategy.py. Example 'Golden Cross' strategy included.

## Demo

___