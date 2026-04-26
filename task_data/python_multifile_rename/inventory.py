from product import Product


def total_value(products: list[Product]) -> float:
    """Return total inventory value in dollars."""
    # BUG: uses old attribute price_cents (now price) and divides by 100 (no longer needed)
    return sum(p.price_cents / 100 for p in products)


def cheapest(products: list[Product]) -> Product | None:
    """Return the cheapest product, or None if the list is empty."""
    if not products:
        return None
    # BUG: uses old attribute price_cents (now price)
    return min(products, key=lambda p: p.price_cents)


def in_category(products: list[Product], category: str) -> list[Product]:
    """Return products belonging to the given category."""
    return [p for p in products if p.category == category]
