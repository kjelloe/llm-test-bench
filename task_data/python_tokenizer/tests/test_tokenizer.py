import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tokenizer import tokenize


def test_plain_string():
    assert tokenize('"hello"') == [("STRING", "hello")]


def test_escaped_newline():
    # \n inside a string should stay inside the STRING token
    result = tokenize(r'"hello\nworld"')
    assert result == [("STRING", r"hello\nworld")], f"got {result!r}"


def test_escaped_backslash():
    # \\ inside a string should produce a single backslash inside STRING
    result = tokenize(r'"ab\\cd"')
    assert result == [("STRING", r"ab\\cd")], f"got {result!r}"


def test_escaped_quote():
    # \" inside a string should not close the string
    result = tokenize(r'"say \"hi\""')
    assert result == [("STRING", r'say \"hi\"')], f"got {result!r}"


def test_escape_does_not_break_subsequent_content():
    # After an escape sequence the tokenizer must remain inside STRING,
    # so the characters after the escape are part of the same token.
    result = tokenize(r'"a\nb"')
    assert len(result) == 1, f"expected 1 token, got {result!r}"
    assert result[0][0] == "STRING", f"expected STRING, got {result!r}"
    assert result[0][1] == r"a\nb", f"expected a\\nb, got {result[0][1]!r}"


def test_multiple_escapes_in_one_string():
    result = tokenize(r'"x\ny\nz"')
    assert result == [("STRING", r"x\ny\nz")], f"got {result!r}"


def test_mixed_tokens():
    result = tokenize('hello 42 "world"')
    assert result == [("WORD", "hello"), ("NUMBER", "42"), ("STRING", "world")]


def test_string_then_word_without_space():
    # After closing quote, WORD token should start cleanly
    result = tokenize('"hi"there')
    assert result == [("STRING", "hi"), ("WORD", "there")], f"got {result!r}"


def test_number_token():
    assert tokenize("123") == [("NUMBER", "123")]


def test_word_token():
    assert tokenize("abc") == [("WORD", "abc")]
