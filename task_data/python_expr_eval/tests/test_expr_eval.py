import pytest
from expr_eval import evaluate


# --- single-operator expressions (correct even with swapped precedence) ---

def test_addition():
    assert evaluate("1 + 2") == 3

def test_subtraction():
    assert evaluate("10 - 3") == 7

def test_multiplication():
    assert evaluate("3 * 4") == 12

def test_integer_division():
    assert evaluate("15 / 3") == 5

def test_left_assoc_subtraction():
    # 10 - 3 - 2 = (10 - 3) - 2 = 5
    assert evaluate("10 - 3 - 2") == 5

def test_left_assoc_division():
    # 100 / 5 / 4 = (100 / 5) / 4 = 5
    assert evaluate("100 / 5 / 4") == 5


# --- parentheses ---

def test_parens_override_precedence():
    assert evaluate("(2 + 3) * 4") == 20

def test_parens_in_both_operands():
    assert evaluate("(10 + 5) / (2 + 1)") == 5

def test_nested_parens():
    assert evaluate("((2 + 3) * (1 + 1))") == 10


# --- mixed-precedence expressions (fail when * / have lower precedence than + -) ---

def test_mul_before_add():
    # correct: 2 + (3 * 4) = 14   wrong (swapped): (2 + 3) * 4 = 20
    assert evaluate("2 + 3 * 4") == 14

def test_div_before_sub():
    # correct: 10 - (4 / 2) = 8   wrong (swapped): (10 - 4) / 2 = 3
    assert evaluate("10 - 4 / 2") == 8

def test_mul_before_sub():
    # correct: 20 - 3 * 5 = 5     wrong (swapped): (20 - 3) * 5 = 85
    assert evaluate("20 - 3 * 5") == 5

def test_mixed_mul_add():
    # correct: (2 * 3) + (4 * 5) = 26
    assert evaluate("2 * 3 + 4 * 5") == 26

def test_complex_expression():
    # correct: 1 + (2 * 3) - (4 / 2) + 5 = 1 + 6 - 2 + 5 = 10
    assert evaluate("1 + 2 * 3 - 4 / 2 + 5") == 10

def test_precedence_chain():
    # correct: (3 * 4) + (10 / 2) - 1 = 12 + 5 - 1 = 16
    assert evaluate("3 * 4 + 10 / 2 - 1") == 16
