"""
Simulation - Sets up 2 identical stock exchanges, 5 standard traders, and 1 fast trader,
then runs a 6.5-hour trading day in 0.5-second increments.

"""

import random
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from exchange import StockExchange, BUY, SELL
from oms import OMS, Trader
from fast_trader import FastTrader

RANDOM_SEED   = 35
random.seed(RANDOM_SEED)

SECURITIES     = ["A", "B", "C", "D", "E"]
INITIAL_PRICES = {"A": 100.0, "B": 95.0, "C": 110.0, "D": 88.0, "E": 120.0}

MARKET_CLOSE  = 23400   # seconds in a 6.5-hour trading day
TICK          = 0.5     # simulation time step (seconds)
LOG_EVERY     = 240     # how often to record P&L for the graph

NUM_TRADERS   = 5
BANK_BALANCE  = 50_000_000  # each trader's bank account
INITIAL_CASH  = 2_000_000  # each trader's starting trading cash
MIN_SHARES    = 2_000  # random portfolio range
MAX_SHARES    = 8_000

# Router - this sits between exchanges and OMS instances 
# when a trade happens the exchange tells the Router, and the Router passes it to the right trader's OMS 

class Router:

    def __init__(self):
        self._oms_map = {}   # trader_id -> OMS

    def register(self, trader_id, oms_instance):
        # link a trader_id to their OMS so callbacks reach the right place
        self._oms_map[trader_id] = oms_instance

    def on_fill(self, tid, sec, side, qty, price, exch, oid, t):
        # trade executed - forward to trader's OMS to update cash and shares
        if tid in self._oms_map:
            self._oms_map[tid].on_fill(tid, sec, side, qty, price, exch, oid, t)

    def on_cancel(self, tid, oid, reason, exch, t):
        # order cancelled - forward to trader's OMS to release reserved funds
        if tid in self._oms_map:
            self._oms_map[tid].on_cancel(tid, oid, reason, exch, t)

# Exchanges
# two identical exchanges, both connected to the same Router
# prices are seeded so traders have a valid reference on the very first tick

router = Router()

# Two identical exchanges 
ex_a = StockExchange("Ex-A", router)
ex_b = StockExchange("Ex-B", router)
exchanges = [ex_a, ex_b]

for sec in SECURITIES:
    ex_a.addSecurity(sec)
    ex_b.addSecurity(sec)
    # seed last traded price on both exchanges before any trading begins
    ex_a.books[sec].lastTradedPrice = INITIAL_PRICES[sec]
    ex_b.books[sec].lastTradedPrice = INITIAL_PRICES[sec]

# Five standard traders with random starting portfolios 
# initial_bank_balance is saved seperately because bank_balance changes during the day as traders top up their trading accounts from the bank 
traders = []
for i in range(NUM_TRADERS):
    tid = f"T-{i + 1}"
    oms = OMS()

    # create trader - registers itself with OMS internally
    t = Trader(tid, BANK_BALANCE, INITIAL_CASH, oms)
    # save starting bank for accurate P&L calculation later
    t.initial_bank_balance = BANK_BALANCE

    # assign random shares per security - done after Trader() since
    # register_trader() resets the portfolio to empty
    for sec in SECURITIES:
        oms.portfolio[tid][sec] = random.randint(MIN_SHARES, MAX_SHARES)

    # snapshot starting wealth = cash + portfolio at opening prices
    # this is used as the baseline when calculating end-of-day P&L
    oms.snapshot_initial_value(tid, INITIAL_PRICES)

    router.register(tid, oms)
    traders.append(t)

# one fast trader - starts with no shares, profits from arbitrage only
ft = FastTrader("FT-1", exchanges, SECURITIES, INITIAL_CASH, BANK_BALANCE)
router.register(ft.trader_id, ft.oms)

def mid_prices():
    # average of last traded price on both exchanges - used to value portfolios
    return {
        sec: (ex_a.getLastPrice(sec) + ex_b.getLastPrice(sec)) / 2
        for sec in SECURITIES
    }

# storage for P&L graph data
total_ticks = int(MARKET_CLOSE / TICK)  # 46800 total ticks
pnl_history = {t.id: [] for t in traders}
pnl_history[ft.trader_id] = []
time_points = []

print("=" * 60)
print("  JPMorgan Quant Finance Mentorship — Trading Simulation")
print("=" * 60)
print(f"  Securities : {', '.join(SECURITIES)}")
print(f"  Traders    : {NUM_TRADERS} standard + 1 fast")
print(f"  Duration   : {MARKET_CLOSE / 3600:.1f} hours  ({total_ticks:,} ticks)")
print("=" * 60)
print("Running...\n")

# run the trading day tick by tick
for step in range(1, total_ticks + 1):
    
    # current simulation time rounded to avoid floating point drift
    t_curr = round(step * TICK, 1)
    is_integer_second = (t_curr % 1.0 == 0.0)

    if is_integer_second:
        # standard traders act every integer second on each security
        for trader in traders:
            if trader.can_trade(SECURITIES):  # skip if no cash and no shares
                for sec in SECURITIES:
                    trader.take_action(exchanges, sec, t_curr)
    else:
        # fast trader scans for arbitrage every x.5 second
        ft.act(t_curr)

    # record P&L snapshot every LOG_EVERY ticks for the graph
    if step % LOG_EVERY == 0:
        mp = mid_prices()
        time_points.append(t_curr)

        for trader in traders:
            # current wealth = trading cash + portfolio value + remaining bank
            current_value = (
                trader.oms.cash[trader.id]
                + trader.oms.portfolio_value(trader.id, mp)
                + trader.bank_balance
            )

            # baseline = initial net worth + initial bank at open
            baseline = trader.oms.initial_net_worth[trader.id] + trader.initial_bank_balance
            pnl_history[trader.id].append(current_value - baseline)

        # fast trader P&L = current total value vs what it started with
        ft_value = ft.total_account_value(mp)
        pnl_history[ft.trader_id].append(ft_value - ft.initial_total)

# cancel all orders still sitting on the books at end of day
ex_a.closeMarket()
ex_b.closeMarket()

# print final P&L table - portfolio valued at EOD mid-market prices
mp = mid_prices()
print("\n" + "=" * 55)
print(f"  {'Trader':<10}  {'Final P&L (₹)':>20}  {'Status'}")
print("-" * 55)

all_results = {}

for trader in traders:
    # final wealth = trading cash + portfolio at EOD prices + remaining bank
    final_value = (
        trader.oms.cash[trader.id]
        + trader.oms.portfolio_value(trader.id, mp)
        + trader.bank_balance
    )
    # baseline uses stored initial_bank_balance for accurate comparison
    baseline = trader.oms.initial_net_worth[trader.id] + trader.initial_bank_balance
    pnl = final_value - baseline
    all_results[trader.id] = pnl
    status = "PROFIT" if pnl >= 0 else "LOSS"
    print(f"  {trader.id:<10}  {pnl:>+20,.2f}  {status}")

# fast trader never holds shares so P&L is purely cash in vs cash out
ft_final = ft.total_account_value(mp)
ft_pnl = ft_final - ft.initial_total
all_results[ft.trader_id] = ft_pnl
status = "PROFIT" if ft_pnl >= 0 else "LOSS"
print(f"  {'FT-1':<10}  {ft_pnl:>+20,.2f}  {status}")
print("=" * 55)

# print closing prices on both exchanges for reference
print("\nEnd-of-day prices:")
for sec in SECURITIES:
    pa = ex_a.getLastPrice(sec)
    pb = ex_b.getLastPrice(sec)
    print(f"  {sec:<6}  Ex-A: {pa:.2f}  Ex-B: {pb:.2f}  Mid: {(pa+pb)/2:.2f}")

#Plots - standard traders on top, fast trader below
# x-axis is time in hours, y-axis is P&L in USD
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 10))
fig.suptitle("JPMorgan Quant Finance — Trader P&L Over Trading Day", fontsize=14, fontweight="bold")

# convert time from seconds to hours for readability
time_hours = [t / 3600 for t in time_points]

# Subplot 1: Standard Traders
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
for trader, color in zip(traders, colors):
    ax1.plot(time_hours, pnl_history[trader.id], label=trader.id, color=color, linewidth=1.5)

ax1.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.6)
ax1.set_title("Standard Traders — P&L Over Time")
ax1.set_ylabel("P&L (INR)")
ax1.set_xlabel("Time (hours)")
ax1.legend(loc="upper left")
ax1.grid(True, alpha=0.3)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))

# Subplot 2: Fast Trader
ax2.plot(time_hours, pnl_history[ft.trader_id],
         label="FT-1 (Arbitrage)", color="#8B0000", linewidth=2)
ax2.axhline(0, color="black", linestyle="--", linewidth=0.8, alpha=0.6) #zero line 
ax2.set_title("Fast Trader (FT-1) — Arbitrage P&L Over Time")
ax2.set_ylabel("P&L (INR)")
ax2.set_xlabel("Time (hours)")
ax2.legend(loc="upper left")
ax2.grid(True, alpha=0.3)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"₹{x:,.0f}"))

plt.tight_layout()
plt.savefig("pnl_graph.png", dpi=150, bbox_inches="tight")
print("\nP&L graph saved to pnl_graph.png")
plt.show()