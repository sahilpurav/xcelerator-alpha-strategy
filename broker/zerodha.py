import os
import re
import time
from urllib.parse import parse_qs, urlparse

import onetimepass as otp
import requests
import typer
from kiteconnect import KiteConnect

from config import Config
from utils.cache import load_from_file, save_to_file


class ZerodhaBroker:
    def __init__(self):
        self.api_key = Config.KITE_APP_KEY
        self.api_secret = Config.KITE_APP_SECRET
        self.app_user_name = Config.KITE_APP_USERNAME
        self.app_password = Config.KITE_APP_PASSWORD
        self.app_totp_key = Config.KITE_APP_TOTP_KEY
        self.token_file = os.path.join("cache/secrets", "zerodha_access_token.txt")
        self.kite = KiteConnect(api_key=self.api_key)

        # auto connect on init
        self._connect()

    def _connect(self):
        # Check if access_token already exists and is valid
        access_token = load_from_file(self.token_file)
        if access_token:
            self.kite.set_access_token(access_token)
            try:
                self.kite.profile()
                print("✅ Using existing token.")
                return
            except:
                print("⚠️  Token invalid, need new login.")

        print("🔗 Generating new session via login flow...")
        credentials = {
            "username": self.app_user_name,
            "password": self.app_password,
            "totp_key": self.app_totp_key,
            "api_key": self.api_key,
            "api_secret": self.api_secret,
        }

        # ✅ Validation: check for missing or empty values
        missing_keys = [key for key, value in credentials.items() if not value]
        if missing_keys:
            raise ValueError(
                f"❌ Missing or empty credentials for: {', '.join(missing_keys)}"
            )

        request_token = self.get_request_token(credentials)

        try:
            session = self.kite.generate_session(
                request_token, api_secret=self.api_secret
            )
            access_token = session["access_token"]
            self.kite.set_access_token(access_token)

            # ✅ Save the token using our cache system
            save_to_file(access_token, self.token_file)

            print("✅ Session established and token saved.")
        except Exception as e:
            print(f"❌ Error generating session: {e}")

    def get_current_positions(self):
        """
        Fetches current CNC positions from Zerodha and returns
        a list of dicts with Symbol, Quantity, and Avg. Buy Price.
        """
        positions = self.kite.positions()["net"]
        rows = []

        for pos in positions:
            if pos.get("product") != "CNC":
                continue

            qty = pos.get("quantity", 0)
            if qty == 0:
                continue

            rows.append(
                {
                    "symbol": pos.get("tradingsymbol"),
                    "action": "BUY" if qty > 0 else "SELL",
                    "buy_price": pos.get("average_price"),
                    "quantity": qty,
                }
            )

        return rows

    def get_holdings(self) -> list[dict]:
        """
        Fetches current holdings from Zerodha and returns
        a list of dicts with Symbol, Quantity, and Avg. Buy Price.
        Merges holdings with same-day CNC positions.
        """
        holdings_raw = self.kite.holdings()
        positions_raw = self.kite.positions()["net"]

        holdings = {}

        # Step 1: Start with holdings (quantity + t1)
        for h in holdings_raw:
            symbol = h["tradingsymbol"]
            total_qty = h["quantity"] + h["t1_quantity"]
            if total_qty > 0:
                holdings[symbol] = {
                    "symbol": symbol,
                    "quantity": total_qty,
                    "buy_price": h["average_price"],
                    "last_price": h["last_price"],
                }

        # Step 2: Add or merge CNC positions (same-day buys)
        for p in positions_raw:
            if p["product"] != "CNC" or p["quantity"] <= 0:
                continue

            symbol = p["tradingsymbol"]
            qty = p["quantity"]
            price = p["average_price"]
            last_price = p["last_price"]

            if symbol in holdings:
                # Merge if already in holdings
                existing = holdings[symbol]
                total_qty = existing["quantity"] + qty
                # Weighted average buy price
                total_invested = (existing["quantity"] * existing["buy_price"]) + (
                    qty * price
                )
                avg_price = total_invested / total_qty
                holdings[symbol] = {
                    "symbol": symbol,
                    "quantity": total_qty,
                    "buy_price": avg_price,
                    "last_price": last_price,
                }
            else:
                holdings[symbol] = {
                    "symbol": symbol,
                    "quantity": qty,
                    "buy_price": price,
                    "last_price": last_price,
                }

        return list(holdings.values())

    def ltp(self, symbols):
        """
        Fetches the latest LTP (Last Traded Price) for a list of symbols.
        Returns a dict with symbol as key and its LTP as value.
        """
        ltp_data = self.kite.ltp(["NSE:" + symbol for symbol in symbols])
        return {
            symbol.replace("NSE:", ""): data["last_price"]
            for symbol, data in ltp_data.items()
        }

    def cash(self):
        """
        Fetches current cash balance from Zerodha and returns
        a dict with available, used, and total cash.
        """
        try:
            margins = self.kite.margins("equity")
            return margins["available"]["live_balance"]
        except Exception as e:
            print(f"❌ Failed to fetch available funds: {e}")
            return None

    def place_order(
        self, symbol, quantity, exchange="NSE", transaction_type="BUY", price=None
    ):
        try:
            order_type = self.kite.ORDER_TYPE_MARKET if price is None else self.kite.ORDER_TYPE_LIMIT
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=order_type,
                product=self.kite.PRODUCT_CNC,
                price=price,
            )
            print(f"✅ Order placed: {order_id}")
            return order_id
        except Exception as e:
            print(f"❌ Failed to place order for {symbol}: {e}")
            return None

    def get_request_token(self, credentials: dict) -> str:
        """
        Handles the login flow to get a request token for Zerodha Kite API.
        This method performs the following steps:
        1. Initiates a session and fetches the login page.
        2. Submits the user credentials (username and password).
        3. Calculates the TOTP timing to avoid expiration.
        4. Submits the TOTP code for two-factor authentication.
        5. Extracts the request token from the redirect URL after successful login.
        """
        session = requests.Session()
        response = session.get(self.kite.login_url())

        # User login POST request
        login_payload = {
            "user_id": credentials["username"],
            "password": credentials["password"],
        }
        login_response = session.post(
            "https://kite.zerodha.com/api/login", login_payload
        )

        # Calculate TOTP timing to avoid expiration
        current_time = int(time.time())
        time_window = current_time % 30  # Position within current 30-second window

        # If we're in the last 10 seconds of the window, wait for the next window
        if time_window > 20:
            wait_time = 30 - time_window + 1  # Wait for next window + 1 second buffer
            print(
                f"⏳ TOTP window expires in {30 - time_window} seconds, waiting {wait_time} seconds for fresh token..."
            )
            time.sleep(wait_time)

        # TOTP POST request
        totp_payload = {
            "user_id": credentials["username"],
            "request_id": login_response.json()["data"]["request_id"],
            "twofa_value": otp.get_totp(credentials["totp_key"]),
            "twofa_type": "totp",
            "skip_session": True,
        }
        totp_response = session.post("https://kite.zerodha.com/api/twofa", totp_payload)

        if totp_response.status_code != 200:
            raise RuntimeError(
                f"❌ TOTP failed with status {totp_response.status_code}. Message: {totp_response.text}"
            )

        # Extract request token from redirect URL
        try:
            response = session.get(self.kite.login_url())
            parse_result = urlparse(response.url)
            query_params = parse_qs(parse_result.query)

            if "request_token" not in query_params:
                raise RuntimeError(
                    "Login succeeded but request_token not found in URL."
                )

        except Exception as e:
            # In our case since the local server is not running, we will get an exception
            # This is a workaround to extract the request token from the error response
            # Uncomment the next line to see the full error message

            # print("Exception caught while parsing URL:", e)
            pattern = r"request_token=([A-Za-z0-9]+)"
            match = re.search(pattern, str(e))
            if match:
                query_params = {"request_token": [match.group(1)]}
            else:
                raise RuntimeError(
                    "Unable to extract request token from error response."
                )

        return query_params["request_token"][0]
