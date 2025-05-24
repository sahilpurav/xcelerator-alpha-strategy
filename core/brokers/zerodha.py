import os
from kiteconnect import KiteConnect
from dotenv import load_dotenv

class ZerodhaBroker:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("KITE_APP_KEY")
        self.api_secret = os.getenv("KITE_APP_SECRET")
        self.token_file = "access_token.txt"
        self.kite = KiteConnect(api_key=self.api_key)

    def connect(self):
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
        print("🔗 Visit this URL to get your request token:")
        print(self.kite.login_url())
        request_token = input("Paste request_token from redirected URL: ").strip()

        try:
            session = self.kite.generate_session(request_token, api_secret=self.api_secret)
            access_token = session["access_token"]
            self.kite.set_access_token(access_token)
            with open(self.token_file, "w") as f:
                f.write(access_token)
            print("✅ Session established and token saved.")
        except Exception as e:
            print(f"❌ Error generating session: {e}")

    def get_holdings(self):
        return self.kite.holdings()

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