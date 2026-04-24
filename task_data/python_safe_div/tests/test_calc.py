import pytest
from calc import safe_div


def test_normal_division():
    assert safe_div(10, 2) == 5.0


def test_float_division():
    assert safe_div(7, 2) == 3.5


def test_negative_divisor():
    assert safe_div(-6, 2) == -3.0


def test_zero_raises_value_error():
    with pytest.raises(ValueError):
        safe_div(5, 0)


def test_zero_zero_raises_value_error():
    with pytest.raises(ValueError):
        safe_div(0, 0)
