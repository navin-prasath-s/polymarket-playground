from py_clob_client.client import ClobClient

class ClobService:
    host = "https://clob.polymarket.com"

    # TODO: pre filter the markets
    @staticmethod
    def get_clob_markets_accepting_orders() -> list[dict]:
        """Fetch all CLOB markets and return those who accepts orders."""
        open_client: ClobClient = ClobClient(host=ClobService.host)
        start_cursor = "MA=="
        end_cursor = "LTE="

        all_markets = []
        next_cursor = start_cursor
        while next_cursor != end_cursor:
            response = open_client.get_markets(next_cursor=next_cursor)

            markets = response.get("data", [])
            all_markets.extend(markets)

            next_cursor = response.get("next_cursor")

        filtered = [
            m for m in all_markets
            if m.get("enable_order_book") and m.get("accepting_orders")
        ]

        return filtered

    @staticmethod
    def get_clob_market_by_condition_id(condition_id: str) -> dict | None:
        """Fetch a single CLOB market by its condition ID."""
        open_client: ClobClient = ClobClient(host=ClobService.host)

        try:
            response = open_client.get_market(condition_id)
            return response
        except Exception as e:
            print(f"Error fetching market for condition_id {condition_id}: {e}")
            return None


    @staticmethod
    def get_market_price_by_token_id(token_id: str) -> dict[str, str] | None:
        """Fetch the market price for a given token ID."""
        open_client: ClobClient = ClobClient(host=ClobService.host)

        try:
            response_buy = open_client.get_price(token_id, side="BUY")
            response_sell = open_client.get_price(token_id, side="SELL")
            if not response_buy or not response_sell:
                print(f"No price data found for token_id {token_id}")
                return None
            prices = {
                "buy": response_buy.get("price"),
                "sell": response_sell.get("price")
            }
            return prices
        except Exception as e:
            print(f"Error fetching market price for token_id {token_id}: {e}")
            return None


    @staticmethod
    def get_book_by_token_id(token_id: str,
                             side: str | None = None) -> (dict[str, list[dict[str, str]]] |
                                                          list[dict[str, str]]| None):
        """Fetch the order book for a given token ID."""
        open_client: ClobClient = ClobClient(host=ClobService.host)

        try:
            response = open_client.get_order_book(token_id)
            bids = [{"price": bid.price, "size": bid.size} for bid in response.bids]
            asks = [{"price": ask.price, "size": ask.size} for ask in response.asks]

            if side is not None:
                if side == "BUY":
                    return asks
                elif side == "SELL":
                    return bids
                else:
                    raise ValueError(f"Invalid side: {side}. Use 'BUY' or 'SELL'.")

            return {"bids": bids, "asks": asks}

        except Exception as e:
            print(f"Error fetching order book for token_id {token_id}: {e}")
            return None


