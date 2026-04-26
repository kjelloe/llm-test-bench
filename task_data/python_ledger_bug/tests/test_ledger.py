import pytest
from ledger import Ledger, InsufficientFunds
from account import Account


def test_successful_transfer():
    ledger = Ledger()
    a = Account('alice', 500)
    b = Account('bob', 100)
    ledger.transfer(a, b, 200)
    assert a.balance == 300
    assert b.balance == 300


def test_successful_transfer_is_logged():
    ledger = Ledger()
    a = Account('alice', 500)
    b = Account('bob', 100)
    ledger.transfer(a, b, 150)
    assert len(ledger.transactions) == 1


def test_insufficient_funds_raises():
    ledger = Ledger()
    a = Account('alice', 100)
    b = Account('bob', 50)
    with pytest.raises(InsufficientFunds):
        ledger.transfer(a, b, 200)


def test_failed_transfer_source_unchanged():
    ledger = Ledger()
    a = Account('alice', 100)
    b = Account('bob', 50)
    try:
        ledger.transfer(a, b, 200)
    except InsufficientFunds:
        pass
    assert a.balance == 100


def test_failed_transfer_destination_unchanged():
    ledger = Ledger()
    a = Account('alice', 100)
    b = Account('bob', 50)
    try:
        ledger.transfer(a, b, 200)
    except InsufficientFunds:
        pass
    assert b.balance == 50


def test_failed_transfer_not_logged():
    ledger = Ledger()
    a = Account('alice', 100)
    b = Account('bob', 50)
    try:
        ledger.transfer(a, b, 200)
    except InsufficientFunds:
        pass
    assert len(ledger.transactions) == 0
