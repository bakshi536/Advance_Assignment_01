import itertools
import random
from exchange import Order, BUY, SELL  # adjust import if your exchange module has a different name

# Global order-id counter so every order across all traders is unique
_counter = itertools.count(1)

def next_order_id():
    return next(_counter)


class OMS:
    # Tracks trading cash + holdings per trader, and updates them on fills.
    # Also performs basic checks before placing BUY (cash) / SELL (shares) orders.
    def __init__(self):
        self.cash = {}               # {tid: trading_cash}
        self.portfolio = {}          # {tid: {sec: qty}}
        self.initial_net_worth = {}  # {tid: start_value for P&L}

    # Account management
    def register_trader(self, tid, initial_cash):
        self.cash[tid] = initial_cash
        self.portfolio[tid] = {}

    def deposit(self, tid, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.cash[tid] += amount

    def withdraw(self, tid, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self.cash[tid]:
            raise ValueError("Insufficient trading cash to withdraw.")
        self.cash[tid] -= amount

    # Valuation helpers
    def portfolio_value(self, tid, prices):
        # Mark-to-market holdings using latest prices dict: {sec: price}
        return sum(qty * prices.get(sec, 0) for sec, qty in self.portfolio[tid].items())

    def total_account_value(self, tid, prices):
        return self.cash[tid] + self.portfolio_value(tid, prices)

    def snapshot_initial_value(self, tid, prices):
        self.initial_net_worth[tid] = self.total_account_value(tid, prices)

    # Order placement
    def place_buy_order(self, tid, exchange, security, price, quantity, timestamp):
        # Skip if not enough trading cash for worst-case spend (limit price * qty)
        if self.cash[tid] < price * quantity:
            return None
        order = Order(next_order_id(), tid, security, BUY, price, quantity, timestamp)
        exchange.submitOrder(order)
        return order

    def place_sell_order(self, tid, exchange, security, price, quantity, timestamp):
        # Skip if trader doesn't hold enough shares
        if self.portfolio[tid].get(security, 0) < quantity:
            return None
        order = Order(next_order_id(), tid, security, SELL, price, quantity, timestamp)
        exchange.submitOrder(order)
        return order
      
    # Exchange callbacks (via Router)
    def on_fill(self, tid, security, side, qty, price, exchange_name, order_id, timestamp):
        # BUY: cash down, shares up; SELL: cash up, shares down
        if side == BUY:
            self.cash[tid] -= qty * price
            self.portfolio[tid][security] = self.portfolio[tid].get(security, 0) + qty
        else:
            self.cash[tid] += qty * price
            self.portfolio[tid][security] = self.portfolio[tid].get(security, 0) - qty

    def on_cancel(self, tid, order_id, reason, exchange_name, timestamp):
        # No reservation model here, so cancel does not change balances (can be logged if needed)
        pass


class Trader:
    # Acts at integer times: chooses BUY/SELL, chooses price, chooses exchange, places order via OMS.
    AUTO_DEPOSIT_THRESHOLD = 200_000
    AUTO_DEPOSIT_AMOUNT = 2_000_000
    ORDER_QUANTITY = 1000
    FALLBACK_PCT = 0.05  # used if no quotes exist (±5% around last price)

    def __init__(self, trader_id, bank_balance, trading_cash, oms):
        self.id = trader_id
        self.bank_balance = bank_balance
        self.oms = oms
        self.oms.register_trader(trader_id, trading_cash)

    # Stop conditions helpers
    def has_cash(self):
        return self.oms.cash[self.id] > 0 or self.bank_balance > 0

    def has_shares(self, securities):
        return any(self.oms.portfolio[self.id].get(s, 0) > 0 for s in securities)

    def can_trade(self, securities):
        return self.has_cash() or self.has_shares(securities)

    # Bank -> trading auto deposit
    def _maybe_deposit(self):
        if self.oms.cash[self.id] < self.AUTO_DEPOSIT_THRESHOLD and self.bank_balance > 0:
            amount = min(self.AUTO_DEPOSIT_AMOUNT, self.bank_balance)
            self.bank_balance -= amount
            self.oms.deposit(self.id, amount)

    # Price selection
    def _choose_price(self, exchanges, stock):
        bids = [ex.getBestBid(stock) for ex in exchanges]
        asks = [ex.getBestAsk(stock) for ex in exchanges]
        bids = [b for b in bids if b is not None]
        asks = [a for a in asks if a is not None]

        if not bids or not asks:
            last = exchanges[0].getLastPrice(stock)
            return round(last * random.choice([1 - self.FALLBACK_PCT, 1 + self.FALLBACK_PCT]), 2)

        best_bid = max(bids)
        best_ask = min(asks)
        mid = round((best_bid + best_ask) / 2, 2)
        return random.choice([best_bid, best_ask, mid])

    # Exchange selection
    def _choose_exchange(self, exchanges, stock, side, price):
        # If one exchange already has the same-side level, send to the other; else random
        has = [ex.hasPriceLevel(stock, side, price) for ex in exchanges]
        if has[0] and not has[1]:
            return exchanges[1]
        if has[1] and not has[0]:
            return exchanges[0]
        return random.choice(exchanges)

    # One action on one stock at time T
    def take_action(self, exchanges, stock, current_time):
        self._maybe_deposit()

        side = random.choice([BUY, SELL])
        price = self._choose_price(exchanges, stock)
        target = self._choose_exchange(exchanges, stock, side, price)

        if side == BUY:
            self.oms.place_buy_order(self.id, target, stock, price, self.ORDER_QUANTITY, current_time)
        else:
            self.oms.place_sell_order(self.id, target, stock, price, self.ORDER_QUANTITY, current_time)
