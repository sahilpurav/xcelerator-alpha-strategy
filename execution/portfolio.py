from broker.zerodha import ZerodhaBroker
from logic.display import display_portfolio_table


def run_holdings_display(tsv: bool = False):
    """Display current holdings and their details."""
    broker = ZerodhaBroker()
    portfolio = broker.get_holdings()

    display_portfolio_table(
        portfolio,
        label_map={
            "symbol": ("Symbol", 12),
            "quantity": ("Quantity", 10),
            "buy_price": ("Average Price", 20),
            "last_price": ("Close Price", 20),
        },
        tsv=tsv,
    )


def run_positions_display(tsv: bool = False):
    """Display current positions and their details."""
    broker = ZerodhaBroker()
    positions = sorted(broker.get_current_positions(), key=lambda x: x["action"])

    display_portfolio_table(
        positions,
        label_map={
            "symbol": ("Symbol", 12),
            "action": ("Action", 10),
            "buy_price": ("Average Price", 20),
            "quantity": ("Quantity", 10),
        },
        tsv=tsv,
    )
