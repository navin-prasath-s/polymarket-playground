import os
import time
from decimal import Decimal
from typing import Any, Dict, Optional, Iterable


import httpx

url = "http://127.0.0.1:8000"

_LEVELS = {"L1": 1, "L2": 2}

class BaseClient:
    """
    Internal base with full logic. Do not instantiate directly.
    Subclasses (e.g., Client) inherit endpoints via mixins.
    """

    def __new__(cls, *args, **kwargs):
        if cls is BaseClient:
            raise TypeError("BaseClient is internal. Use `Client(...)` instead.")
        return super().__new__(cls)

    def __init__(
        self,
        url: str,
        *,
        timeout: float = 5.0,
        retries: int = 3,
        backoff: float = 0.5,
        l1_key: Optional[str] = None,
        l2_key: Optional[str] = None,
    ):
        self.base_url = url.rstrip("/")

        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff

        self.l1_key = l1_key or os.getenv("L1_KEY")
        self.l2_key = l2_key or os.getenv("L2_KEY")

        self.permissions = set()
        if self.l1_key:
            self.permissions.add("L1")
        if self.l2_key:
            self.permissions.add("L2")

        self._client = httpx.Client(timeout=self.timeout, base_url=self.base_url)


    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _check_access(self, required: Optional[str]):
        """Raise if trying to call a protected endpoint without permission."""
        if required is None:
            return  # open endpoint
        if required not in self.permissions:
            available = ", ".join(self.permissions) if self.permissions else "none"
            raise PermissionError(
                f"{required} permission required for this endpoint. "
                f"Available permissions: {available}"
            )

    def _headers_for(self, required: Optional[str]) -> Dict[str, str]:
        if required == "L1" and self.l1_key:
            return {"X-API-Key": self.l1_key}
        if required == "L2" and self.l2_key:
            return {"X-API-Key": self.l2_key}
        return {}


    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Dict[str, Any] | None = None,
        json: Dict[str, Any] | None = None,
        required: Optional[str] = None,
    ) -> httpx.Response:
        self._check_access(required)
        headers = self._headers_for(required)

        last_exc = None
        for attempt in range(1, self.retries + 1):
            try:
                resp = self._client.request(method, path, params=params, json=json, headers=headers)
                resp.raise_for_status()
                return resp
            except (httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_exc = e
                if attempt == self.retries:
                    raise
                time.sleep(self.backoff * (2 ** (attempt - 1)))
        raise last_exc or RuntimeError("Unknown request failure")



class Client(BaseClient):
    """
       Public client.
       Usage:
           client = Client(url="http://127.0.0.1:8000", allow=("L1","L2"))
           client.get_health()
       """


    def get_health(self) -> Dict[str, Any]:
        """Get health status of the server."""
        return self._request("GET", "/").json()



    def create_user(self, name: str, balance: Decimal|str|None = None):
        """
        Create a new user.
        If `balance` is omitted (None), the server will use its default (10000.00).
        """
        payload = {"name": name}
        if balance is not None:
            payload["balance"] = str(balance)  # str() for Decimal safety in JSON

        return self._request("POST", "/users/", json=payload).json()


    def get_user(self, name: str):
        """
        Fetch a user by name.
        Returns JSON from the API (dict with 'name' and 'balance').
        """
        return self._request("GET", f"/users/{name}").json()


    def reset_user_balance(self, name: str, balance: Decimal | float | str | None = None):
        """
        Reset a user's balance (requires L1 key).
        If `balance` is None, the server resets it to 10000.00.
        """
        payload = {} if balance is None else {"balance": str(balance)}
        try:
            return self._request(
                "PATCH",
                f"/users/{name}/reset-balance",
                json=payload,
                required="L1",
            ).json()
        except httpx.HTTPStatusError as e:
            print("STATUS:", e.response.status_code)
            print("BODY:", e.response.text)
            raise



    def buy(
            self,
            *,
            user_name: str,
            market: str,
            token: str,
            amount_usdc: Decimal | float | str,
            order_type: str = "MARKET"
    ):
        """
        Create a market BUY order.
        Server route: POST /orders/buy
        """
        payload = {
            "user_name": user_name,
            "market": market,
            "token": token,
            "amount_usdc": str(amount_usdc),
            "order_type": order_type,
        }
        return self._request("POST", "/orders/buy", json=payload).json()


    def sell(
            self,
            *,
            user_name: str,
            market: str,
            token: str,
            shares: Decimal | float | str,
            order_type: str = "MARKET"
    ):
        """
        Create a market SELL order.
        Server route: POST /orders/sell
        """
        payload = {
            "user_name": user_name,
            "market": market,
            "token": token,
            "shares": str(shares),
            "order_type": order_type,
        }
        return self._request("POST", "/orders/sell", json=payload).json()

    def list_orders(self):
        """
        GET /orders/ — returns all orders (with fills included by the server).
        """
        return self._request("GET", "/orders/").json()


    def list_orders_by_user(self, user_name: str):
        """
        GET /orders/{user_name} — returns all orders placed by the user.
        """
        return self._request("GET", f"/orders/{user_name}").json()


    def list_positions(self):
        """
        GET /positions — returns all user positions in the system.
        """
        return self._request("GET", "/positions").json()


    def list_positions_by_user(self, user_name: str):
        """
        GET /positions/{user_name} — returns all positions for the given user.
        Raises HTTP 404 if the user does not exist.
        """
        return self._request("GET", f"/positions/{user_name}").json()


    def delete_all_data(self):
        """
        DELETE /admin/clear-all  (L2 required)
        Wipes users, markets, orders, positions, logs. Returns {"success": True, ...}
        """
        return self._request("DELETE", "/admin/clear-all", required="L2").json()


    def exec_sql(self, sql: str, params: dict | None = None, limit: int = 500):
        """
        POST /admin/exec-sql (L2 required)
        Executes arbitrary SQL.
        - SELECT: returns {"columns": [...], "rows": [...], "truncated": bool}
        - DML/DDL: returns {"affected_rows": int}
        """
        payload = {"sql": sql, "limit": limit}
        if params and ":" in sql:
            payload["params"] = params
        return self._request("POST", "/admin/exec-sql", json=payload, required="L2").json()

