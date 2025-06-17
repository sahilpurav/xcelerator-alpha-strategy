from twilio.rest import Client
from dotenv import load_dotenv
import os


load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
whatsapp_to = os.getenv("TWILIO_WHATSAPP_TO")
is_twilio_enabled = os.getenv("ENABLE_TWILIO_WHATSAPP", "false").strip().lower() == "true"


client = Client(account_sid, auth_token)

def send_whatsapp_message(message_body=None, type='portfolio'):
    """Send a WhatsApp message via Twilio.
    
    Args:
        message_body (str, optional): The message content.
            If not provided, a default message is used.
    
    Returns:
        str: The Message SID if sent successfully.
    """
    if message_body is None:
        return 
    
    
    message_body = format_portfolio_summary(message_body)

    # print (type(message_body))
    # print(f"📱 Sending WhatsApp message: {message_body}")

    if(is_twilio_enabled):
        # print(f"📱 Sending WhatsApp message: {message_body}")
        message = client.messages.create(
            body=message_body,
            from_=whatsapp_from,
            to=whatsapp_to
        )
        return message.sid

def format_portfolio_summary(df, char_limit=1500):
    import pandas as pd

    from datetime import datetime

    # Timestamp
    now = datetime.now().strftime("🕒 %d %b %Y, %H:%M")

    # Clean column names
    df.columns = [col.strip() for col in df.columns]

    # Round price
    df['Price'] = df['Price'].round(2)

    # SELL section
    sell_rows = df[df['Action'].str.upper() == 'SELL']
    sell_lines = [
        f"{row['Symbol']}({row['Price']}, {int(row['Quantity'])})"
        for _, row in sell_rows.iterrows()
    ]
    sell_text = "SELL:\n" + ", ".join(sell_lines) if sell_lines else ""

    # HOLD section
    hold_rows = df[df['Action'].str.upper() == 'HOLD']
    hold_lines = [
        f"{row['Symbol']}(#%s)" % int(row['Rank']) if str(row['Rank']).isdigit() else f"{row['Symbol']}(#NA)"
        for _, row in hold_rows.iterrows()
    ]
    hold_chunks = [", ".join(hold_lines[i:i+4]) for i in range(0, len(hold_lines), 4)]
    hold_text = "HOLD:\n" + "\n".join(hold_chunks) if hold_chunks else ""

    # BUY section
    buy_rows = df[df['Action'].str.upper() == 'BUY']
    buy_lines = [
        f"{row['Symbol']}({row['Price']}, {int(row['Quantity'])})"
        for _, row in buy_rows.iterrows()
    ]
    buy_chunks = [", ".join(buy_lines[i:i+3]) for i in range(0, len(buy_lines), 3)]
    buy_text = "BUY:\n" + "\n".join(buy_chunks) if buy_chunks else ""

    # Summary
    before_value = df['Invested'].sum()
    after_value = df[df['Action'].str.upper() != 'SELL']['Invested'].sum()
    summary = (
        "\n\nSummary:\n"
        f"Before: ₹{before_value:,.2f}\n"
        f"After: ₹{after_value:,.2f}"
    )

    # Attempt with HOLD included
    parts_with_hold = [now, sell_text, hold_text, buy_text]
    message = "\n\n".join([p for p in parts_with_hold if p]) + summary

    if len(message) <= char_limit:
        return message

    # Try without HOLD
    parts_without_hold = [now, sell_text, buy_text]
    message = "\n\n".join([p for p in parts_without_hold if p]) + summary

    # Add note that HOLD was removed
    note = "\n⚠️ HOLD section omitted to stay within 1500 characters."
    if len(message + note) <= char_limit:
        message += note

    return message



if __name__ == '__main__':
    sid = send_whatsapp_message()
    print(f"Message sent with SID: {sid}")