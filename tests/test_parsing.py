from lib.parsing import FileEdit, parse_file_blocks, validate_edits


def test_single_block():
    text = "BEGIN_FILE src/foo.py\nprint('hello')\nEND_FILE"
    edits = parse_file_blocks(text)
    assert len(edits) == 1
    assert edits[0].path == "src/foo.py"
    assert edits[0].content == "print('hello')\n"


def test_multiple_blocks():
    text = "BEGIN_FILE a.py\nx = 1\nEND_FILE\nBEGIN_FILE b.py\ny = 2\nEND_FILE"
    edits = parse_file_blocks(text)
    assert len(edits) == 2
    assert edits[0].path == "a.py"
    assert edits[1].path == "b.py"


def test_empty_string_returns_no_blocks():
    assert parse_file_blocks("") == []


def test_plain_text_returns_no_blocks():
    assert parse_file_blocks("Here is some text without any blocks.") == []


def test_multiline_content():
    text = (
        "BEGIN_FILE calc.py\n"
        "def safe_div(a, b):\n"
        "    if b == 0:\n"
        "        raise ValueError('zero')\n"
        "    return a / b\n"
        "END_FILE"
    )
    edits = parse_file_blocks(text)
    assert len(edits) == 1
    assert "raise ValueError" in edits[0].content


def test_blocks_mixed_with_surrounding_text():
    text = (
        "Here is the fix:\n"
        "BEGIN_FILE src/foo.py\nx = 1\nEND_FILE\n"
        "That should do it."
    )
    edits = parse_file_blocks(text)
    assert len(edits) == 1
    assert edits[0].path == "src/foo.py"


def test_path_with_subdirectory():
    text = "BEGIN_FILE src/deep/nested/file.js\nconsole.log('hi');\nEND_FILE"
    edits = parse_file_blocks(text)
    assert edits[0].path == "src/deep/nested/file.js"


def test_validate_edits_all_allowed():
    edits = [FileEdit("src/foo.py", "x=1")]
    assert validate_edits(edits, ["src/foo.py"]) == []


def test_validate_edits_forbidden_file():
    edits = [FileEdit("src/foo.py", "x=1"), FileEdit("Makefile", "")]
    violations = validate_edits(edits, ["src/foo.py"])
    assert len(violations) == 1
    assert "Makefile" in violations[0]


def test_validate_edits_empty_list():
    assert validate_edits([], ["src/foo.py"]) == []


def test_dedent_strips_uniform_leading_whitespace():
    # codestral outputs all lines with 3-space leading indent inside BEGIN_FILE blocks
    text = (
        "BEGIN_FILE calc.py\n"
        "   def safe_div(a, b):\n"
        "       if b == 0:\n"
        "           raise ValueError('zero')\n"
        "       return a / b\n"
        "END_FILE"
    )
    edits = parse_file_blocks(text)
    assert len(edits) == 1
    assert edits[0].content.startswith("def safe_div")
    assert "raise ValueError" in edits[0].content


def test_dedent_preserves_relative_indentation():
    # dedent strips common prefix only — relative indentation must survive
    text = (
        "BEGIN_FILE foo.py\n"
        "   x = 1\n"
        "   if x:\n"
        "       y = 2\n"
        "END_FILE"
    )
    edits = parse_file_blocks(text)
    content = edits[0].content
    assert content.startswith("x = 1")
    assert "    y = 2" in content  # 4-space indent relative to stripped baseline


def test_validate_all_forbidden():
    edits = [FileEdit("secret.py", "")]
    violations = validate_edits(edits, ["src/foo.py"])
    assert len(violations) == 1
    assert "secret.py" in violations[0]
