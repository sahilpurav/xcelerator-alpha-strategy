import math

import pandas as pd


def _allocate_capital_equally_with_cap(
    stocks: list[dict[str, str | float | int]], usable_capital: float, max_cap_per_stock: float
) -> tuple[list[dict[str, str | float | int]], float]:
    """
    Step 1: Equal allocation amongst given stocks with maximum cap per stock.

    For held stocks: Only allocates ADDITIONAL capital needed to reach target
    For new stocks: Allocates full target amount

    Args:
        stocks: List of dicts with 'symbol', 'last_price', 'rank', 'quantity'
        usable_capital: Total capital available for allocation (net of transaction costs)
        max_cap_per_stock: Maximum total value per stock (target allocation)

    Returns:
        Tuple of (allocations, leftover_capital)
        - allocations: List of dicts with 'symbol', 'rank', 'price', 'quantity', 'invested'
        - leftover_capital: Remaining capital after allocation
    """
    if not stocks or usable_capital <= 0:
        return [], usable_capital

    # Step 1: Equal distribution among zero-quantity stocks first
    total_allocated = 0
    updated_stocks = []
    zero_quantity_stocks = [stock for stock in stocks if stock["quantity"] == 0]
    if zero_quantity_stocks:
        amount_per_zero_stock = min(
            (usable_capital / len(zero_quantity_stocks)), max_cap_per_stock
        )

        for stock in stocks:
            if stock["quantity"] == 0:
                # This is a zero-quantity stock, allocate equal share
                symbol = stock["symbol"]
                price = stock["last_price"]
                rank = stock["rank"]

                # Calculate shares we can buy with equal share
                shares_to_buy = math.floor(amount_per_zero_stock / price)
                actual_investment = shares_to_buy * price

                # Create updated stock with new quantity
                updated_stock = stock.copy()
                updated_stock["quantity"] = shares_to_buy
                updated_stocks.append(updated_stock)

                total_allocated += actual_investment
            else:
                # Keep held stocks as-is for now
                updated_stocks.append(stock.copy())
    else:
        # No zero-quantity stocks, use original stocks
        updated_stocks = [stock.copy() for stock in stocks]

    # Step 2: Sort all stocks (including recently filled) by quantity and fill remaining capital
    sorted_stocks = sorted(
        updated_stocks, key=lambda x: x["quantity"] * x["last_price"]
    )

    allocations = []

    for stock in sorted_stocks:
        symbol = stock["symbol"]
        price = stock["last_price"]
        rank = stock["rank"]
        current_quantity = stock["quantity"]

        # Calculate current value of this stock
        current_value = current_quantity * price

        # Calculate target value for this stock
        target_value = max_cap_per_stock

        # Calculate additional capital needed to reach target
        additional_capital_needed = max(0, target_value - current_value)

        # Calculate how much we can actually allocate (limited by remaining usable capital)
        remaining_usable_capital = usable_capital - total_allocated
        additional_capital_to_allocate = min(
            additional_capital_needed, remaining_usable_capital
        )

        # Calculate additional shares we can buy
        if additional_capital_to_allocate > 0:
            additional_shares = math.floor(additional_capital_to_allocate / price)
            additional_invested = additional_shares * price
        else:
            additional_shares = 0
            additional_invested = 0

        # Calculate final quantities and values
        final_quantity = current_quantity + additional_shares

        # Add allocation record
        allocations.append(
            {
                "symbol": symbol,
                "rank": rank,
                "last_price": price,
                "quantity": final_quantity,
            }
        )

        total_allocated += additional_invested

    leftover_capital = usable_capital - total_allocated
    return allocations, leftover_capital


def _allocate_leftover_iterative_equal_distribution(
    allocations: list[dict[str, str | float | int]], leftover_capital: float
) -> tuple[list[dict[str, str | float | int]], float]:
    """
    Step 2: Iterative Equal Distribution - distributes leftover capital equally across all stocks
    in multiple rounds until remaining capital is less than the cheapest stock price.

    Args:
        allocations: List of allocation dicts from Step 1
        leftover_capital: Remaining capital to distribute

    Returns:
        Tuple of (updated_allocations, remaining_capital)
    """
    if leftover_capital <= 0 or not allocations:
        return allocations, leftover_capital

    remaining_capital = leftover_capital

    # Continue distributing until no more allocations can be made
    while remaining_capital > 0:
        # Sort stocks by invested value (lowest invested first) for balanced allocation
        sorted_allocations = sorted(
            allocations, key=lambda x: x["last_price"] * x["quantity"]
        )

        # Track if any allocation was made in this round
        any_allocation_made = False

        # Try to buy 1 share for the stock with lowest invested value first
        for allocation in sorted_allocations:
            price = allocation["last_price"]

            if remaining_capital >= price:
                # Buy 1 more share
                allocation["quantity"] += 1
                remaining_capital -= price
                any_allocation_made = True
                break  # Only allocate to one stock per round (lowest invested)

        # If no allocations were made in this round, break to avoid infinite loop
        if not any_allocation_made:
            break

    # Convert back to original order (maintain input order)
    symbol_to_allocation = {alloc["symbol"]: alloc for alloc in sorted_allocations}
    updated_allocations = [
        symbol_to_allocation[original["symbol"]] for original in allocations
    ]

    return updated_allocations, remaining_capital


def _validate_inputs(
    held_stocks: list[dict[str, str | float | int]],
    new_stocks: list[dict[str, str | float | int]],
    removed_stocks: list[dict[str, str | float | int]],
    transaction_cost_pct: float,
) -> None:
    """
    Validates all inputs for smart rebalance function.

    Args:
        held_stocks: List of dicts for stocks to keep holding
        new_stocks: List of dicts for stocks to buy
        removed_stocks: List of dicts for stocks to sell
        transaction_cost_pct: Transaction cost percentage

    Raises:
        ValueError: If any validation fails
    """
    # 1. Parameter validation
    if (
        not isinstance(transaction_cost_pct, (int, float))
        or transaction_cost_pct < 0
        or transaction_cost_pct >= 1
    ):
        raise ValueError(
            f"transaction_cost_pct must be between 0 and 1, got: {transaction_cost_pct}"
        )

    # 2. At least one category must have data
    if not held_stocks and not new_stocks and not removed_stocks:
        raise ValueError(
            "At least one of held_stocks, new_stocks, or removed_stocks must be non-empty"
        )

    # 3. Business logic validation
    if removed_stocks and not new_stocks:
        raise ValueError(
            "If there are removed_stocks, there must be new_stocks to deploy the freed capital"
        )

    # 4. Data structure validation for each category
    def validate_stock_list(
        stocks: list[dict], category_name: str, expected_quantity_rule: str
    ):
        if not isinstance(stocks, list):
            raise ValueError(f"{category_name} must be a list")

        for i, stock in enumerate(stocks):
            if not isinstance(stock, dict):
                raise ValueError(f"{category_name}[{i}] must be a dictionary")

            # Required fields
            required_fields = ["symbol", "last_price", "rank", "quantity"]
            for field in required_fields:
                if field not in stock:
                    raise ValueError(
                        f"{category_name}[{i}] missing required field: '{field}'"
                    )

            # Symbol validation
            if not isinstance(stock["symbol"], str) or not stock["symbol"].strip():
                raise ValueError(
                    f"{category_name}[{i}] 'symbol' must be a non-empty string"
                )

            # Price validation
            if (
                not isinstance(stock["last_price"], (int, float))
                or stock["last_price"] <= 0
            ):
                raise ValueError(
                    f"{category_name}[{i}] 'last_price' must be a positive number"
                )

            # Rank validation (can be None for cash equivalents)
            if stock["rank"] is not None and (
                not isinstance(stock["rank"], int) or stock["rank"] <= 0
            ):
                raise ValueError(
                    f"{category_name}[{i}] 'rank' must be a positive integer or None"
                )

            # Quantity validation
            if not isinstance(stock["quantity"], int) or stock["quantity"] < 0:
                raise ValueError(
                    f"{category_name}[{i}] 'quantity' must be a non-negative integer"
                )

            # Business rule validation for quantities
            if expected_quantity_rule == "zero" and stock["quantity"] != 0:
                raise ValueError(
                    f"{category_name}[{i}] 'quantity' should be 0 for new stocks to buy"
                )
            elif expected_quantity_rule == "positive" and stock["quantity"] <= 0:
                raise ValueError(
                    f"{category_name}[{i}] 'quantity' should be positive for existing holdings"
                )

    # Validate each category
    validate_stock_list(held_stocks, "held_stocks", "positive")
    validate_stock_list(new_stocks, "new_stocks", "zero")
    validate_stock_list(removed_stocks, "removed_stocks", "positive")

    # 5. Cross-category validation (no duplicate symbols)
    all_symbols = []

    for stock in held_stocks:
        all_symbols.append(("held", stock["symbol"]))
    for stock in new_stocks:
        all_symbols.append(("new", stock["symbol"]))
    for stock in removed_stocks:
        all_symbols.append(("removed", stock["symbol"]))

    # Check for duplicates
    symbols_only = [symbol for _, symbol in all_symbols]
    seen_symbols = set()
    duplicates = set()

    for symbol in symbols_only:
        if symbol in seen_symbols:
            duplicates.add(symbol)
        seen_symbols.add(symbol)

    if duplicates:
        # Find which categories have the duplicates
        duplicate_details = {}
        for category, symbol in all_symbols:
            if symbol in duplicates:
                if symbol not in duplicate_details:
                    duplicate_details[symbol] = []
                duplicate_details[symbol].append(category)

        error_msg = "Duplicate symbols found across categories: "
        for symbol, categories in duplicate_details.items():
            error_msg += f"{symbol} in {categories}, "
        raise ValueError(error_msg.rstrip(", "))


def plan_allocation(
    held_stocks: list[dict],
    new_stocks: list[dict],
    removed_stocks: list[dict],
    cash: float = 0.0,
    transaction_cost_pct: float = 0.001192,
):
    """Plan a rebalance based on current holdings and new entries."""

    # Validate inputs first
    _validate_inputs(
        held_stocks, new_stocks, removed_stocks, transaction_cost_pct
    )

    # Calculate freed capital from removed stocks
    sell_value = sum(
        stock["quantity"] * stock["last_price"] for stock in removed_stocks
    )
    freed_capital = cash + sell_value

    if freed_capital <= 0:
        print("✅ Nothing to rebalance.")
        return pd.DataFrame(
            data=[],
            columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested"],
        )

    # Calculate transaction costs
    buy_value = freed_capital  # Assuming we'll use all freed capital for purchases
    total_traded_value = sell_value + buy_value
    transaction_cost = total_traded_value * transaction_cost_pct
    usable_capital = freed_capital - transaction_cost

    all_portfolio_stocks = held_stocks + new_stocks

    # Calculate total portfolio value (held capital + usable capital)
    held_capital = sum(stock["quantity"] * stock["last_price"] for stock in held_stocks)
    total_portfolio_capital = held_capital + usable_capital

    max_cap_per_stock = total_portfolio_capital / len(all_portfolio_stocks)

    # Step 1: Apply equal allocation with cap to entire portfolio
    allocations, leftover_capital = _allocate_capital_equally_with_cap(
        stocks=all_portfolio_stocks,
        usable_capital=usable_capital,
        max_cap_per_stock=max_cap_per_stock,
    )

    # Step 2: Distribute leftover capital iteratively across all stocks
    allocations, leftover_capital = _allocate_leftover_iterative_equal_distribution(
        allocations=allocations, leftover_capital=leftover_capital
    )

    # Iterate over allocations and see if any stock has 0 quantity,
    # if so, print a message saying not enough capital to buy portfolio and exit
    for allocation in allocations:
        if allocation["quantity"] == 0:
            print(
                f"❌ Insufficient capital: Cannot allocate funds to all {len(allocations)} stocks."
            )
            print(f"💰 Please add more funds to your broker account.")
            return pd.DataFrame(
                data=[],
                columns=["Symbol", "Rank", "Action", "Price", "Quantity", "Invested"],
            )

    # Prepare execution data
    execution_data = []

    # Add SELL orders for removed stocks
    if len(removed_stocks) > 0:
        for stock in removed_stocks:
            execution_data.append(
                {
                    "Symbol": stock["symbol"],
                    "Rank": stock["rank"] if stock["rank"] is not None else "N/A",
                    "Action": "SELL",
                    "Price": round(stock["last_price"], 2),
                    "Quantity": int(stock["quantity"]),
                    "Invested": round((stock["quantity"] * stock["last_price"]), 2),
                }
            )

    # Create lookup for original quantities
    previous_quanitities = {
        stock["symbol"]: stock["quantity"] for stock in all_portfolio_stocks
    }

    # Add BUY/HOLD orders from allocations
    for allocation in allocations:
        symbol = allocation["symbol"]
        final_quantity = allocation["quantity"]
        price = allocation["last_price"]
        rank = allocation["rank"]

        # Get original quantity (0 for new stocks)
        previous_quantity = previous_quanitities.get(symbol, 0)

        # If this was a held stock, show the existing position first
        if previous_quantity > 0:
            execution_data.append(
                {
                    "Symbol": symbol,
                    "Rank": rank if rank is not None else "N/A",
                    "Action": "HOLD",
                    "Price": round(price, 2),
                    "Quantity": int(previous_quantity),
                    "Invested": round(previous_quantity * price, 2),
                }
            )

        # Calculate additional shares being purchased
        additional_shares = final_quantity - previous_quantity

        # If we're buying additional shares, add the purchase order
        if additional_shares > 0:
            # For new stocks (previous_quantity = 0), this is a BUY
            # For held stocks (previous_quantity > 0), this is also a BUY (additional purchase)
            action = "BUY"

            execution_data.append(
                {
                    "Symbol": symbol,
                    "Rank": rank if rank is not None else "N/A",
                    "Action": action,
                    "Price": round(price, 2),
                    "Quantity": int(additional_shares),
                    "Invested": round(additional_shares * price, 2),
                }
            )

    execution_data = sorted(execution_data, key=lambda x: (x["Action"]), reverse=True)

    return pd.DataFrame(execution_data)
