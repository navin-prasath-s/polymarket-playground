from decimal import Decimal, ROUND_DOWN


class OrderService:

    @staticmethod
    def simulate_buy_transaction(amount: Decimal,
                                    book: list[dict]) -> dict:
        amount_left = Decimal(amount)
        total_shares = Decimal("0")
        total_cost = Decimal("0")
        fills = []

        levels = sorted(book, key=lambda x: Decimal(x['price']))

        for level in levels:
            price = Decimal(level['price'])
            size = Decimal(level['size'])
            possible_cost = price * size

            if possible_cost <= amount_left:
                # Can buy all at this price
                total_shares += size
                total_cost += possible_cost
                fills.append({
                    "fill_price": price,
                    "fill_shares": size
                })

                amount_left -= possible_cost
            else:
                # Can only buy part at this price
                shares_affordable = amount_left / price
                if shares_affordable > 0:
                    total_shares += shares_affordable
                    total_cost += shares_affordable * price
                    fills.append({
                        "fill_price": price,
                        "fill_shares": shares_affordable
                    })
                break

        if total_cost < Decimal(amount):
            return {
                "status": "exceeds_liquidity",
                "max_amount": total_cost.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
                "max_shares": total_shares.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
                "fills": fills
            }

        return {
            "status": "filled",
            "shares_filled": total_shares.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            "total_cost": total_cost.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            "fills": fills
        }

    @staticmethod
    def simulate_sell_transaction(shares: Decimal,
                                 book: list[dict]) -> dict:
        shares_left = Decimal(shares)
        total_shares = Decimal("0")
        total_proceeds = Decimal("0")
        fills = []

        levels = sorted(book, key=lambda x: Decimal(x['price']), reverse=True)

        for level in levels:
            price = Decimal(level['price'])
            size = Decimal(level['size'])

            if size <= shares_left:
                # Can sell all at this price
                fill_shares = size
                total_shares += fill_shares
                total_proceeds += fill_shares * price
                fills.append({
                    "fill_price": price,
                    "fill_shares": fill_shares
                })
                shares_left -= fill_shares
            else:
                # Can only buy part at this price
                fill_shares = shares_left
                if fill_shares > 0:
                    total_shares += fill_shares
                    total_proceeds += fill_shares * price
                    fills.append({
                        "fill_price": price,
                        "fill_shares": fill_shares
                    })
                shares_left = Decimal("0")
                break

        if total_shares < Decimal(shares):
            return {
                "status": "exceeds_liquidity",
                "max_shares": total_shares.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
                "max_amount": total_proceeds.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
                "fills": fills
            }

        return {
            "status": "filled",
            "shares_sold": total_shares.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            "total_proceeds": total_proceeds.quantize(Decimal("0.01"), rounding=ROUND_DOWN),
            "fills": fills
        }


