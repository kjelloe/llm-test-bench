class InsufficientFunds(Exception):
    pass


class Ledger:
    def __init__(self):
        self.transactions = []

    def transfer(self, from_acc, to_acc, amount):
        to_acc.balance += amount
        if from_acc.balance < amount:
            raise InsufficientFunds(
                f"{from_acc.name} has {from_acc.balance}, cannot transfer {amount}"
            )
        from_acc.balance -= amount
        self.transactions.append((from_acc.name, to_acc.name, amount))
