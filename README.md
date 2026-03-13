# Advance_Assignment_01
A stock exchange simulation implementing order matching, trader behaviour and cross-exchange arbitrage over a 6.5-hour trading day.

---

## Overview
This project simulates a realistic stock market environment with two identical exchanges, five standard traders, and one fast trader. All components communicate through a central router that dispatches exchange notifications to the correct trader's order management system. The simulation runs in 0.5-second increments over a 6.5-hour trading day, tracking P&L for every participant in real time.

## File Breakdown
exchange-engine.py

Implements the core exchange infrastructure. Each exchange hosts up to five securities, each with its own independent order book. Orders are stored in heaps to maintain price-time priority —> buy orders in a max-heap (highest price first) and sell orders in a min-heap (lowest price first). When a new order arrives it is immediately matched against the opposite side of the book. If the best bid is greater than or equal to the best ask, a trade is executed at the passive order's price (the older order sets the price). After every order insertion the top-5 rule is enforced — any order outside the best 5 on either side is immediately cancelled and the trader is notified via the router. At end of day all remaining resting orders are cancelled. The exchange exposes market data methods for last traded price, best bid, best ask, and top 5 bids and offers.

oms+trader.py

Implements the Order Management System and the standard Trader. The OMS tracks trading cash and portfolio holdings per trader and acts as the only permitted route for placing orders on the exchange. When a buy order is placed, cash is reserved immediately to prevent overspending. When a sell order is placed, shares are locked immediately to prevent overselling. When the exchange reports a fill via the router, the OMS credits shares on a buy fill and credits cash on a sell fill. The Trader class sits on top of the OMS and implements the trading logic required by the assignment — randomly choosing buy or sell with equal probability, selecting a price from best bid, best ask, or mid-price, and choosing which exchange to send the order to based on whether that price level already exists on one of the exchanges. If no quotes exist on either exchange, the trader places an order 5% above or below the last traded price. Traders automatically top up their trading account from their bank balance when cash runs low, and stop trading entirely when both cash and shares are exhausted.

fast_trader.py

Implements the Fast Trader which operates at every half-second tick. The fast trader's strategy is pure cross-exchange arbitrage — at every x.5 second it scans all five securities across both exchanges looking for situations where the ask price on one exchange is strictly lower than the bid price on the other. When such a discrepancy is found it simultaneously places a buy order on the cheaper exchange and a sell order on the more expensive one, locking in a guaranteed risk-free profit. Before placing any order it verifies that sufficient size exists on both sides of the book and that enough cash is available. The fast trader maintains its own separate OMS account and never holds shares beyond what is needed to complete an arbitrage pair.

simulation.py

The main entry point that wires all components together and runs the simulation. It creates two identical exchanges connected to a central router, registers five standard traders each with a random starting portfolio of 2,000 to 8,000 shares per security, and initialises one fast trader. The simulation runs for 46,800 ticks covering a 6.5-hour trading day. At every integer second the standard traders act on each security. At every half-second the fast trader scans for arbitrage. P&L is recorded periodically throughout the day by marking each trader's portfolio to mid-market prices across both exchanges. At end of day all resting orders are cancelled, final P&L is printed to console for all participants, and a two-panel graph is saved showing standard trader P&L on top and fast trader P&L below.

## How to Run

### 1. Install dependencies
```
bashpip install matplotlib
```

### 2. Ensure all files are in the same directory
```
exchange.py
oms.py
fast_trader.py
simulation.py
```

### 3. Run the simulation
```
python simulation.py
```

### 4. Output

- P&L summary table printed to console at end of day
- pnl_graph.png saved to the current directory showing P&L over time for all traders


## Requirements: 

- Python 3.8+
- matplotlib

