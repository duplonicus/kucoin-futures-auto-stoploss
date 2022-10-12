# kucoin-futures-auto-stoploss
Automatically manage stop orders for active positions

The purpose of this script is to prevent liquidation events. It creates a reduce-only stop order the specified amount of tick-sizes away from the liquidation price when a new position is entered, cancels the stop order if the position is closed, or resubmits the stop order if the size or liquidation price of the position changes. Even though the stop is only a few ticks away from the liquidation price, being stopped out is better than being liquidated because it preserves your maintenance margin. More info on this [here](https://medium.com/@Austerity_Sucks/why-you-should-never-use-your-liquidation-price-as-a-stop-loss-on-bitcoin-futures-30655f280ddd).

Add your API connection info to secret.ini.

[api]  
key =  
secret =  
passphrase = 
