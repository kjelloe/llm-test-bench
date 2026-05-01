class Lexer:
    def __init__(self, text: str):
        self.tokens: list[tuple[str, object]] = []
        i = 0
        while i < len(text):
            if text[i].isspace():
                i += 1
            elif text[i].isdigit():
                j = i
                while j < len(text) and text[j].isdigit():
                    j += 1
                self.tokens.append(("NUM", int(text[i:j])))
                i = j
            elif text[i] in "+-*/()":
                self.tokens.append(("OP", text[i]))
                i += 1
            else:
                raise ValueError(f"Unknown character: {text[i]!r}")
        self.pos = 0

    def peek(self) -> tuple[str, object]:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("EOF", None)

    def consume(self) -> tuple[str, object]:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok


class Parser:
    """Recursive-descent parser for integer arithmetic expressions.

    Grammar:
        expr   = term  (('+' | '-') term)*
        term   = factor (('*' | '/') factor)*
        factor = NUMBER | '(' expr ')'

    Precedence (low → high): addition/subtraction → multiplication/division → atoms.
    All binary operators are left-associative.
    Division is integer (floor) division.
    """

    def __init__(self, text: str):
        self.lex = Lexer(text)

    def parse(self) -> int:
        result = self.expr()
        if self.lex.peek()[0] != "EOF":
            raise ValueError(f"Unexpected token: {self.lex.peek()}")
        return result

    def expr(self) -> int:
        left = self.term()
        while self.lex.peek() in (("OP", "*"), ("OP", "/")):
            op = self.lex.consume()[1]
            right = self.term()
            left = left * right if op == "*" else left // right
        return left

    def term(self) -> int:
        left = self.factor()
        while self.lex.peek() in (("OP", "+"), ("OP", "-")):
            op = self.lex.consume()[1]
            right = self.factor()
            left = left + right if op == "+" else left - right
        return left

    def factor(self) -> int:
        tok = self.lex.peek()
        if tok[0] == "NUM":
            return self.lex.consume()[1]
        if tok == ("OP", "("):
            self.lex.consume()
            val = self.expr()
            if self.lex.peek() != ("OP", ")"):
                raise ValueError("Expected ')'")
            self.lex.consume()
            return val
        raise ValueError(f"Unexpected token: {tok}")


def evaluate(expression: str) -> int:
    """Evaluate an integer arithmetic expression and return the result."""
    return Parser(expression).parse()
