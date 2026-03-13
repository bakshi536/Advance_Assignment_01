"""
Fast Trader.

- Acts at half-integer times (0.5, 1.5, 2.5, ...).
- Cross-exchange arbitrage: buy on the exchange with lower ask and sell on the other with higher bid.
- Executes only when ask < bid (so both legs should fill immediately in the same tick).
"""

from exchange import Order, BUY, SELL
from oms import OMS, next_order_id


class FastTrader:
    ORDER_QUANTITY = 1000

    def __init__(self, trader_id, exchanges, securities, initial_cash, bank_balance):
        self.trader_id = trader_id
        self.exchanges = exchanges      # exactly 2 exchanges
        self.securities = securities
        self.bank_balance = bank_balance

        # Used for end-of-day profit/loss
        self.initial_total = initial_cash + bank_balance

        # Fast trader uses its own OMS account (cash only at start; no shares required)
        self.oms = OMS()
        self.oms.register_trader(trader_id, initial_cash)

    # Called at every x.5 second tick
    def act(self, t):
        # For each security, check both directions:
        #   buy on A sell on B, and buy on B sell on A
        ex_a, ex_b = self.exchanges

        for sec in self.securities:
            ask_a = ex_a.getBestAsk(sec)
            bid_a = ex_a.getBestBid(sec)
            ask_b = ex_b.getBestAsk(sec)
            bid_b = ex_b.getBestBid(sec)

            # Buy cheap on A, sell high on B
            if ask_a is not None and bid_b is not None and ask_a < bid_b:
                self._execute_arb(sec, buy_ex=ex_a, sell_ex=ex_b,
                                  buy_price=ask_a, sell_price=bid_b, t=t)

            # Buy cheap on B, sell high on A
            if ask_b is not None and bid_a is not None and ask_b < bid_a:
                self._execute_arb(sec, buy_ex=ex_b, sell_ex=ex_a,
                                  buy_price=ask_b, sell_price=bid_a, t=t)

    def _execute_arb(self, sec, buy_ex, sell_ex, buy_price, sell_price, t):
        # Place simultaneous BUY + SELL legs.
        # We only check cash for the buy leg; the sell is intended to be covered by the buy in the same tick.
        qty = self.ORDER_QUANTITY
        cash_needed = buy_price * qty

        if self.oms.cash[self.trader_id] < cash_needed:
            return  # skip to avoid entering a one-sided position

        buy_order = Order(next_order_id(), self.trader_id, sec, BUY, buy_price, qty, t)
        sell_order = Order(next_order_id(), self.trader_id, sec, SELL, sell_price, qty, t)

        buy_ex.submitOrder(buy_order)
        sell_ex.submitOrder(sell_order)

    # P&L and value reporting
    def get_pnl(self):
        # Cash-based P&L including bank balance
        current = self.oms.cash[self.trader_id] + self.bank_balance
        return current - self.initial_total

    def total_account_value(self, prices):
        # Mark-to-market: cash + bank + open positions valued at current prices
        port_val = sum(
            qty * prices.get(sec, 0)
            for sec, qty in self.oms.portfolio[self.trader_id].items()
        )
        return self.oms.cash[self.trader_id] + self.bank_balance + port_val