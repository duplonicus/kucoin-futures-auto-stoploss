# kucoin-futures-auto-stoploss

## Features

Automatic stop-losses, trailing stop-losses, and algo-trading.

## About

The main purpose of this script is to prevent liquidation events. When a position exists or is entered, it creates a stoploss order at the specified # of ticks away from the liquidation price, resubmits the order if the position size or liquidation price changes, or cancels the order if the position is closed. The original stoploss is replaced with a trailing-stop at an unrealized ROE percentage determined dynamically based on leverage and the options chosen in stoploss.py.

The orders appear on the Stop Orders tab and the trader can still use the Stop/Take-Profit button on the Positions tab to set a closer stop or take profit. The trader can adjust the 'start_trailing_pcnt_lead', 'leeway_pcnt', and 'trailing_bump_pcnt' to suit their trading style. See examples in stoploss.py.

Even if the stop is only a few ticks away from the liquidation price, provided that it gets hit, being stopped out is better than being liquidated because it preserves your maintenance margin. More info on this [here](https://medium.com/@Austerity_Sucks/why-you-should-never-use-your-liquidation-price-as-a-stop-loss-on-bitcoin-futures-30655f280ddd).

## Installation

<details>
<summary>Instructions
</summary>

1. Clone the repository:

        git clone https://github.com/duplonicus/kucoin-futures-auto-stoploss.git

2. Install [Python 3.10](https://www.python.org/downloads/release/python-3100/) or set up new virtual environment for 3.10.

3. Install the requirements from a terminal in the repository with pip.

        pip install -r requirements.txt

4. Install [SurrealDB](https://surrealdb.com/) and set respective options in stoploss.py to True to enable additional functionality.

5. Create secret.ini in the root of the repository and add your Kucoin API connection info and Discord webhook URL.

        # Example secret.ini file
        [api]
        key =
        secret =
        passphrase =
        [discord]
        webhook_url =

</details>

## Algo-trading

Define your strategy in strategy.py. Example 'Golden Cross' strategy included.

## Demo

