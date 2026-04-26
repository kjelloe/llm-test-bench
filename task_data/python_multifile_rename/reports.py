from product import Product


def price_report(products: list[Product]) -> list[str]:
    """Return one formatted line per product: 'Name: $X.XX'."""
    lines = []
    for p in products:
        # BUG: uses old attribute price_cents and divides by 100 (no longer needed)
        dollars = p.price_cents / 100
        lines.append(f"{p.name}: ${dollars:.2f}")
    return lines


def category_summary(products: list[Product]) -> dict[str, float]:
    """Return total value per category in dollars."""
    totals: dict[str, float] = {}
    for p in products:
        # BUG: uses old attribute price_cents and divides by 100 (no longer needed)
        totals[p.category] = totals.get(p.category, 0.0) + p.price_cents / 100
    return totals
