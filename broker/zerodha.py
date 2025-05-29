import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv
import typer

class ZerodhaBroker:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("KITE_APP_KEY")
        self.api_secret = os.getenv("KITE_APP_SECRET")
        self.token_file = os.path.join("cache/secrets", "zerodha_access_token.txt")
        self.kite = KiteConnect(api_key=self.api_key)
        
        # auto connect on init
        self._connect()

    def _connect(self):
        # Check if access_token already exists and is valid
        if os.path.exists(self.token_file):
            with open(self.token_file, "r") as f:
                token = f.read().strip()
                self.kite.set_access_token(token)
                try:
                    self.kite.profile()
                    print("✅ Session restored from token file.")
                    return
                except:
                    print("⚠️  Token invalid, need new login.")

        # Generate new token via login flow
        print(f"🔗 Visit this URL to get your request token: {self.kite.login_url()}")
        request_token = typer.prompt("🔑 Paste request_token from redirected URL")

        try:
            session = self.kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = session["access_token"]
            self.kite.set_access_token(access_token)
            
            # ✅ Ensure cache/secrets/ exists before saving
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)

            with open(self.token_file, "w") as f:
                f.write(access_token)
            
            print("✅ Session established and token saved.")
        except Exception as e:
            print(f"❌ Error generating session: {e}")

    def get_holdings(self) -> list[dict]:
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
                    "buy_price": h["average_price"]
                }

        # Step 2: Add or merge CNC positions (same-day buys)
        for p in positions_raw:
            if p["product"] != "CNC" or p["quantity"] <= 0:
                continue

            symbol = p["tradingsymbol"]
            qty = p["quantity"]
            price = p["average_price"]

            if symbol in holdings:
                # Merge if already in holdings
                existing = holdings[symbol]
                total_qty = existing["quantity"] + qty
                # Weighted average buy price
                total_invested = (existing["quantity"] * existing["buy_price"]) + (qty * price)
                avg_price = total_invested / total_qty
                holdings[symbol] = {
                    "symbol": symbol,
                    "quantity": total_qty,
                    "buy_price": avg_price
                }
            else:
                holdings[symbol] = {
                    "symbol": symbol,
                    "quantity": qty,
                    "buy_price": price
                }

        return list(holdings.values())


    def place_market_order(self, symbol, quantity, exchange="NSE", transaction_type="BUY"):
        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=exchange,
                tradingsymbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type=self.kite.ORDER_TYPE_MARKET,
                product=self.kite.PRODUCT_CNC
            )
            print(f"✅ Order placed: {order_id}")
            return order_id
        except Exception as e:
            print(f"❌ Failed to place order for {symbol}: {e}")
            return None