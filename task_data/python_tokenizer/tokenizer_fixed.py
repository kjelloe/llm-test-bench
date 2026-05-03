"""
Simple string tokenizer using an explicit state machine.

Token types:
  STRING  — a double-quoted string, supporting escape sequences \\ and \"
  NUMBER  — one or more digit characters
  WORD    — one or more alphabetic characters
  UNKNOWN — any other character

The tokenizer processes input character by character through these states:
  INIT    — between tokens; choose next state based on current character
  STRING  — inside a double-quoted string (after the opening quote)
  ESCAPE  — inside a string, after seeing a backslash
  NUMBER  — accumulating digit characters
  WORD    — accumulating alphabetic characters

Returns a list of (token_type, token_value) tuples.
"""


def tokenize(text: str) -> list[tuple[str, str]]:
    tokens: list[tuple[str, str]] = []
    state = "INIT"
    buf = ""

    for ch in text:
        if state == "INIT":
            if ch == '"':
                state = "STRING"
                buf = ""
            elif ch.isdigit():
                state = "NUMBER"
                buf = ch
            elif ch.isalpha():
                state = "WORD"
                buf = ch
            else:
                if ch not in (" ", "\t", "\n"):
                    tokens.append(("UNKNOWN", ch))

        elif state == "STRING":
            if ch == "\\":
                state = "ESCAPE"
            elif ch == '"':
                tokens.append(("STRING", buf))
                state = "INIT"
                buf = ""
            else:
                buf += ch

        elif state == "ESCAPE":
            buf += ch
            state = "STRING"

        elif state == "NUMBER":
            if ch.isdigit():
                buf += ch
            else:
                tokens.append(("NUMBER", buf))
                buf = ""
                state = "INIT"
                # re-process ch in INIT
                if ch == '"':
                    state = "STRING"
                    buf = ""
                elif ch.isalpha():
                    state = "WORD"
                    buf = ch
                elif ch not in (" ", "\t", "\n"):
                    tokens.append(("UNKNOWN", ch))

        elif state == "WORD":
            if ch.isalpha():
                buf += ch
            else:
                tokens.append(("WORD", buf))
                buf = ""
                state = "INIT"
                # re-process ch in INIT
                if ch == '"':
                    state = "STRING"
                    buf = ""
                elif ch.isdigit():
                    state = "NUMBER"
                    buf = ch
                elif ch not in (" ", "\t", "\n"):
                    tokens.append(("UNKNOWN", ch))

    # flush any in-progress token
    if state == "NUMBER" and buf:
        tokens.append(("NUMBER", buf))
    elif state == "WORD" and buf:
        tokens.append(("WORD", buf))
    elif state == "STRING":
        tokens.append(("STRING", buf))  # unterminated — emit what we have

    return tokens
