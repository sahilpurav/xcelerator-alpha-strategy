import os
from dotenv import load_dotenv

# Load environment variables once at application startup
load_dotenv()

class Config:
    # Twilio/WhatsApp Configuration
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
    TWILIO_WHATSAPP_TO = os.getenv("TWILIO_WHATSAPP_TO")
    ENABLE_TWILIO_WHATSAPP = os.getenv("ENABLE_TWILIO_WHATSAPP", "false").strip().lower() == "true"
    
    # Zerodha/Kite Configuration
    KITE_APP_KEY = os.getenv("KITE_APP_KEY")
    KITE_APP_SECRET = os.getenv("KITE_APP_SECRET")
    KITE_APP_USERNAME = os.getenv("KITE_APP_USERNAME")
    KITE_APP_PASSWORD = os.getenv("KITE_APP_PASSWORD")
    KITE_APP_TOTP_KEY = os.getenv("KITE_APP_TOTP_KEY")
