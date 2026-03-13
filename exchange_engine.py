import heapq

BUY = "BUY"
SELL = "SELL"


class Order:
    # Limit order: BUY/SELL a security with a limit price and quantity at a given timestamp
    def __init__(self, orderId, traderId, security, order_type, price, quantity, timestamp):
        self.orderId = orderId
        self.traderId = traderId
        self.security = security
        self.type = order_type
        self.price = price
        self.quantity = quantity
        self.timestamp = timestamp

    def __repr__(self):
        return (f"Order(id={self.orderId}, trader={self.traderId}, sec={self.security}, "
                f"type={self.type}, price={self.price:.2f}, qty={self.quantity}, t={self.timestamp})")


class Trade:
    # One executed match between a buyer and a seller
    def __init__(self, buyer, seller, security, price, quantity,
                 buyOrderId, sellOrderId, exchangeName, timestamp):
        self.buyer = buyer
        self.seller = seller
        self.security = security
        self.price = price
        self.quantity = quantity
        self.buyOrderId = buyOrderId
        self.sellOrderId = sellOrderId
        self.exchangeName = exchangeName
        self.timestamp = timestamp

    def __repr__(self):
        return (f"Trade({self.security} {self.quantity}@{self.price:.2f} "
                f"buyer={self.buyer} seller={self.seller} on {self.exchangeName} t={self.timestamp})")


class OrderBook:
    # OrderBook for ONE security.
    
    # Price-time priority using heaps:
    #   BUY: (-price, timestamp, orderId, order)  -> higher price first, then earlier time
    #   SELL: ( price, timestamp, orderId, order) -> lower price first, then earlier time
    
    # Router (if provided) receives:
    #   on_fill(...)   when trades happen
    #   on_cancel(...) when orders are cancelled (top-5 / end-of-day)
    def __init__(self, exchangeName, router=None):
        self.exchangeName = exchangeName
        self.router = router

        self.buyOrders = []   # heap entries: (-price, timestamp, orderId, Order)
        self.sellOrders = []  # heap entries: ( price, timestamp, orderId, Order)

        self.lastTradedPrice = 100.0
        self.tradeLog = []
        
    # Market data helpers
    def getBestBid(self):
        return -self.buyOrders[0][0] if self.buyOrders else None

    def getBestAsk(self):
        return self.sellOrders[0][0] if self.sellOrders else None

    def getLastPrice(self):
        return self.lastTradedPrice

    def getTop5Bids(self):
        # sorted() works since heap entries are tuples with the same ordering key
        return [entry[3] for entry in sorted(self.buyOrders)[:5]]

    def getTop5Asks(self):
        return [entry[3] for entry in sorted(self.sellOrders)[:5]]

    def hasPriceLevel(self, side, price):
        # Used by trader logic to check whether a price level already exists on an exchange
        book = self.buyOrders if side == BUY else self.sellOrders
        for entry in book:
            stored_price = -entry[0] if side == BUY else entry[0]
            if abs(stored_price - price) < 1e-6:
                return True
        return False

    # Order entry
    def addOrder(self, order):
        # Insert into book, match if possible, then enforce top-5 constraint
        if order.type == BUY:
            heapq.heappush(self.buyOrders, (-order.price, order.timestamp, order.orderId, order))
        else:
            heapq.heappush(self.sellOrders, (order.price, order.timestamp, order.orderId, order))

        self._matchOrders(order.timestamp)
        self._enforceTop5(order.timestamp)

    # Matching engine
    def _matchOrders(self, now):
        # Keep matching while best bid >= best ask
        while self.buyOrders and self.sellOrders:
            b_neg, b_time, b_id, b = self.buyOrders[0]
            s_price, s_time, s_id, s = self.sellOrders[0]

            best_bid = -b_neg
            if best_bid < s_price:
                break  # book does not cross -> no trade

            # Execute at passive (older) order's price
            trade_price = s_price if s_time <= b_time else best_bid
            qty = min(b.quantity, s.quantity)

            self.lastTradedPrice = trade_price

            # Record the trade (useful for debugging/report output)
            self.tradeLog.append(Trade(
                buyer=b.traderId, seller=s.traderId,
                security=b.security, price=trade_price, quantity=qty,
                buyOrderId=b_id, sellOrderId=s_id,
                exchangeName=self.exchangeName, timestamp=now
            ))

            # Notify Router/OMS so cash/holdings update immediately
            if self.router:
                self.router.on_fill(b.traderId, b.security, BUY, qty, trade_price, self.exchangeName, b_id, now)
                self.router.on_fill(s.traderId, s.security, SELL, qty, trade_price, self.exchangeName, s_id, now)

            # Partial fill support (reduce remaining qty and pop if fully filled)
            b.quantity -= qty
            s.quantity -= qty

            if b.quantity <= 0:
                heapq.heappop(self.buyOrders)
            if s.quantity <= 0:
                heapq.heappop(self.sellOrders)

    # Top-5 enforcement
    def _enforceTop5(self, now):
        # Keep only best 5 orders on each side; cancel the rest
        # BUY: sorted by (-price, time) => best bids first
        if len(self.buyOrders) > 5:
            ordered = sorted(self.buyOrders)
            for _, _, _, o in ordered[5:]:
                if self.router:
                    self.router.on_cancel(o.traderId, o.orderId, "Outside Top 5", self.exchangeName, now)
            self.buyOrders = ordered[:5]
            heapq.heapify(self.buyOrders)

        # SELL: sorted by (price, time) => best asks first
        if len(self.sellOrders) > 5:
            ordered = sorted(self.sellOrders)
            for _, _, _, o in ordered[5:]:
                if self.router:
                    self.router.on_cancel(o.traderId, o.orderId, "Outside Top 5", self.exchangeName, now)
            self.sellOrders = ordered[:5]
            heapq.heapify(self.sellOrders)

    # End-of-day cancel
    def cancelAll(self, now):
        # Cancel all remaining resting orders
        for book in (self.buyOrders, self.sellOrders):
            while book:
                o = heapq.heappop(book)[3]
                if self.router:
                    self.router.on_cancel(o.traderId, o.orderId, "EOD", self.exchangeName, now)


class StockExchange:
    # Exchange hosts up to 5 securities; each security has an independent OrderBook
    MAX_SECURITIES = 5
    MARKET_OPEN = 0
    MARKET_CLOSE = 23400  # 6.5 hours

    def __init__(self, name, router=None):
        self.name = name
        self.router = router
        self.books = {}  # {security: OrderBook}

    def addSecurity(self, sec):
        if len(self.books) >= self.MAX_SECURITIES:
            raise ValueError(f"{self.name}: cannot list more than {self.MAX_SECURITIES} securities.")
        self.books[sec] = OrderBook(self.name, self.router)

    def submitOrder(self, order):
        # Accept only during trading hours; ignore if outside
        if not (self.MARKET_OPEN <= order.timestamp < self.MARKET_CLOSE):
            return
        if order.security not in self.books:
            raise KeyError(f"{self.name}: unknown security '{order.security}'")
        self.books[order.security].addOrder(order)

    # Exchange-level market data
    def getLastPrice(self, sec):
        return self.books[sec].getLastPrice()

    def getBestBid(self, sec):
        return self.books[sec].getBestBid()

    def getBestAsk(self, sec):
        return self.books[sec].getBestAsk()

    def getTop5(self, sec):
        return self.books[sec].getTop5Bids(), self.books[sec].getTop5Asks()

    def hasPriceLevel(self, sec, side, price):
        return self.books[sec].hasPriceLevel(side, price)

    def closeMarket(self):
        for book in self.books.values():
            book.cancelAll(self.MARKET_CLOSE)