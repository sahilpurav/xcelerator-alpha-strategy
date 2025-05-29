def print_portfolio_table(data: list[dict], label_map: dict, tsv: bool = False):
    """
    Prints a formatted table (human-readable or TSV for Google Sheets).
    :param data: List of dicts like [{'symbol': ..., 'quantity': ..., 'buy_price': ...}]
    :param label_map: Dict like {'symbol': ('Symbol', 12), 'quantity': ('Quantity', 10)}
    :param tsv: If True, output tab-separated values (good for Google Sheets)
    """
    if not data:
        print("🚫 No active CNC entries.")
        return

    # Extract header and rows
    headers = [label for _, (label, _) in label_map.items()]
    keys = list(label_map.keys())

    if tsv:
        print("\t".join(headers))
        for row in data:
            print("\t".join(str(row.get(key, "")) for key in keys))
    else:
        header = "".join(f"{label:<{width}}" for _, (label, width) in label_map.items())
        print(header)
        print("-" * len(header))
        for row in data:
            line = "".join(
                f"{str(row.get(key, '')):<{width}}" for key, (_, width) in label_map.items()
            )
            print(line)
