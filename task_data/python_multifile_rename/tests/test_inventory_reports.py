import pytest
from product import Product
from inventory import total_value, cheapest, in_category
from reports import price_report, category_summary


PRODUCTS = [
    Product("Widget",  9.99,  "tools"),
    Product("Gadget",  24.99, "electronics"),
    Product("Doohickey", 4.99, "tools"),
    Product("Thingamajig", 49.99, "electronics"),
]


# inventory tests

def test_total_value():
    assert abs(total_value(PRODUCTS) - 89.96) < 0.01


def test_total_value_empty():
    assert total_value([]) == 0.0


def test_cheapest():
    result = cheapest(PRODUCTS)
    assert result is not None
    assert result.name == "Doohickey"


def test_cheapest_empty():
    assert cheapest([]) is None


def test_in_category():
    tools = in_category(PRODUCTS, "tools")
    assert len(tools) == 2
    assert all(p.category == "tools" for p in tools)


# reports tests

def test_price_report():
    report = price_report([Product("Widget", 9.99, "tools")])
    assert report == ["Widget: $9.99"]


def test_price_report_multiple():
    report = price_report(PRODUCTS[:2])
    assert report == ["Widget: $9.99", "Gadget: $24.99"]


def test_category_summary():
    summary = category_summary(PRODUCTS)
    assert abs(summary["tools"] - 14.98) < 0.01
    assert abs(summary["electronics"] - 74.98) < 0.01
