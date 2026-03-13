# Advance_Assignment_01
A stock exchange simulation implementing order matching, trader behaviour and cross-exchange arbitrage over a 6.5-hour trading day.

--

## Overview
This project simulates a realistic stock market environment consisting of:
- Two identical exchanges
- Five standard traders
- One fast trader (arbitrage trader)
- A central router that routes exchange notifications to each trader’s Order Management System (OMS)

The simulation runs in 0.5-second increments across a 6.5-hour trading session (46,800 ticks).
Throughout the simulation, Profit & Loss (P&L) is tracked in real time for every trader.

## System Architecture

The system consists of four main modules:

├── exchange_engine.py
├── oms+trader.py
├── fast_trader.py
├── simulation.py

Each module represents a core component of the simulated trading system.

## File Breakdown

### 1. exchange_engine.py

This module implements the core exchange infrastructure.
Each exchange supports up to five securities, each with its own independent order book.

#### Order Book Design

Orders are stored using heaps to enforce price–time priority:
- Buy orders → Max heap (highest price first)
- Sell orders → Min heap (lowest price first)

#### Order Matching Logic

When a new order arrives:
1. The exchange checks the opposite side of the order book
2. If best_bid >= best_ask
3. A trade is executed.

The passive order (older order) determines the trade price.

#### Top-5 Rule

After each order insertion:

- Only the top 5 bids and top 5 asks remain active
- Any order outside the top 5 is automatically cancelled
- The trader is notified through the router

#### End-of-Day Behaviour

- All remaining resting orders are cancelled.
- Final market data is recorded.

#### Market Data Methods

The exchange provides:

- Last traded price
- Best bid
- Best ask
- Top 5 bids
- Top 5 asks

### 2. oms+trader.py

This module implements both:

- Order Management System (OMS)
- Standard Trader

#### Order Management System

The OMS acts as the only interface between traders and exchanges.

It tracks:

- Trader cash balance
- Portfolio holdings
- Reserved capital for open orders

#### Risk Controls

When placing orders:

Buy Order
- Cash is reserved immediately
- Prevents overspending

Sell Order
- Shares are locked immediately
- Prevents overselling

#### Fill Handling

When a trade occurs:

|Order Type| OMS Action | 
|----------|----------|
| Buy Fill |Shares credited| 
| Sell Fill|Cash credited | 

#### Standard Trader Strategy

Each trader:
- Randomly selects Buy or Sell (50/50 probability)
- Chooses price from:
+ Best Bid
+ Best Ask
+ Mid-Price

#### Exchange Selection Logic

The trader sends the order to the exchange where the selected price level already exists.

If no quotes exist on either exchange:
- Buy orders are placed 5% above the last traded price
- Sell orders are placed 5% below the last traded price

#### Capital Management

Traders automatically:

- Top up their trading account from their bank balance when cash runs low
- Stop trading when both:
+ Cash = 0
+ Shares = 0

### 3. fast_trader.py

This module implements the Fast Trader, which operates at every 0.5-second tick.

#### Strategy: Cross-Exchange Arbitrage

At each half-second interval, the fast trader scans all securities across both exchanges looking for price discrepancies:

Ask_A < Bid_B
or
Ask_B < Bid_A

When such a condition occurs:

1. Buy on the cheaper exchange
2. Sell on the more expensive exchange

This locks in a risk-free arbitrage profit.

#### Risk Checks Before Trading

Before placing orders the fast trader verifies:

- Sufficient order book depth
- Adequate available cash

The fast trader:

-  Uses its own OMS account
-  Never holds inventory longer than needed to complete the arbitrage pair

### 4. simulation.py

This file is the main entry point of the system.

It performs the following tasks:

#### System Initialization

- Creates two identical exchanges
- Connects them via a central router
- Registers five standard traders
- Initializes one fast trader

Each standard trader starts with:

- 2,000 – 8,000 shares per security (randomized)

### Simulation Timeline

| Event    | Frequency| 
|----------|----------|
| Standard Traders   | Every 1 second  | 
| Fast Trader    | Every 0.5 second | 

Total duration:

46,800 ticks = 6.5 hour trading day

#### P&L Tracking

P&L is periodically calculated by:
````
Portfolio Value = Cash + Mark-to-Market value of holdings
````
Prices are marked using mid-market prices across both exchanges.

#### End-of-Day Actions

At the end of the simulation:

- All remaining orders are cancelled
- Final P&L is printed
- A P&L graph is generated

## How to Run

### 1. Install dependencies
```
pip install matplotlib
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

