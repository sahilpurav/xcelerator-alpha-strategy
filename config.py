import os

from dotenv import load_dotenv

# Load environment variables once at application startup
_ = load_dotenv()


class Config:
    # Twilio/WhatsApp Configuration
    TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_WHATSAPP_FROM: str | None = os.getenv("TWILIO_WHATSAPP_FROM")
    TWILIO_WHATSAPP_TO: str | None = os.getenv("TWILIO_WHATSAPP_TO")
    ENABLE_TWILIO_WHATSAPP: bool = (
        os.getenv("ENABLE_TWILIO_WHATSAPP", "false").strip().lower() == "true"
    )

    # Zerodha/Kite Configuration
    KITE_APP_KEY: str | None = os.getenv("KITE_APP_KEY")
    KITE_APP_SECRET: str | None = os.getenv("KITE_APP_SECRET")
    KITE_APP_USERNAME: str | None = os.getenv("KITE_APP_USERNAME")
    KITE_APP_PASSWORD: str | None = os.getenv("KITE_APP_PASSWORD")
    KITE_APP_TOTP_KEY: str | None = os.getenv("KITE_APP_TOTP_KEY")

    # Cache Configuration
    CACHE_ENABLED: bool = os.getenv("CACHE", "true").strip().lower() == "true"
