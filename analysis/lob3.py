from dataclasses import dataclass, field
from databento_dbn import UNDEF_PRICE

OrderId = int
UnixTimestamp = int


@dataclass
class Order:
    side: str
    price: int
    size: int
    ts_event: UnixTimestamp


@dataclass
class PriceLevel:
    price: int | None = None
    size: int = 0
    count: int = 0


@dataclass
class Book:
    orders: dict[OrderId, Order] = field(default_factory=dict)

    def bbo(self) -> tuple[PriceLevel, PriceLevel]:
        best_ask = PriceLevel()
        best_bid = PriceLevel()
        for order in self.orders.values():
            if order.side == "A":
                if best_ask.price is None or best_ask.price > order.price:
                    best_ask = PriceLevel(
                        price=order.price,
                        size=order.size,
                        count=1,
                    )
                elif best_ask.price == order.price:
                    best_ask.size += order.size
                    best_ask.count += 1
            elif order.side == "B":
                if best_bid.price is None or best_bid.price < order.price:
                    best_bid = PriceLevel(
                        price=order.price,
                        size=order.size,
                        count=1,
                    )
                elif best_bid.price == order.price:
                    best_bid.size += order.size
                    best_bid.count += 1
        return best_bid, best_ask

    def apply(
        self,
        ts_event: UnixTimestamp,
        action: str,
        side: str,
        order_id: int,
        price: int,
        size: int,
    ) -> None:
        # Trade or Fill: no change
        if action == "T" or action == "F":
            return

        # Clear book: remove all resting orders
        if action == "R":
            self.orders.clear()
            return

        # side=N and UNDEF_PRICE are only valid with Trade, Fill, and Clear actions
        assert side == "A" or side == "B"
        if price == UNDEF_PRICE:
            assert size == 0
            return

        # Add: insert a new order
        if action == "A":
            self.orders[order_id] = Order(side, price, size, ts_event)

        # Cancel: partially or fully cancel some size from a resting order
        elif action == "C":
            existing_order = self.orders[order_id]
            assert existing_order.size >= size
            existing_order.size -= size
            # If the full size is cancelled, remove the order from the book
            if existing_order.size == 0:
                self.orders.pop(order_id)

        # Modify: change the price and/or size of a resting order
        elif action == "M":
            existing_order = self.orders[order_id]
            # The order loses its priority if the price changes the same or the size increases
            if existing_order.price != price or existing_order.size < size:
                existing_order.ts_event = ts_event
            existing_order.size = size
            existing_order.price = price
