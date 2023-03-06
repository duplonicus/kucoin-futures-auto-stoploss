# kucoin-futures-auto-stoploss
Automatically manage stop and take-profit orders for active positions

The main purpose of this script is to prevent liquidation events. It creates a reduce-only stop order the specified amount of tick-sizes away from the liquidation price when a new position is entered, cancels the stop order if the position is closed, or resubmits the stop order if the position size or liquidation price changes. It can also create take-profit orders at a specified percentage target. 

Even if the stop is only a few ticks away from the liquidation price, being stopped out is better than being liquidated because it preserves your maintenance margin. More info on this [here](https://medium.com/@Austerity_Sucks/why-you-should-never-use-your-liquidation-price-as-a-stop-loss-on-bitcoin-futures-30655f280ddd).

Add your API connection info to secret.ini.

[api]  
key =  
secret =  
passphrase = 

Note: 

The dev branch includes trailing stop functionality. I haven't merged it because there is an issue where a stop order is placed and immediately cancelled when a stop is hit. Also, it's in the process of being switched from SurrealDB to SQL because it was slowing me down.
