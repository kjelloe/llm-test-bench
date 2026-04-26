from dataclasses import dataclass


@dataclass
class Product:
    name: str
    price: float        # dollars — renamed from price_cents (int, hundredths of a dollar)
    category: str


def format_price(product: "Product") -> str:
    return f"${product.price:.2f}"
