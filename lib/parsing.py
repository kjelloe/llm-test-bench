import re
import textwrap
from dataclasses import dataclass


@dataclass
class FileEdit:
    path: str
    content: str


def parse_file_blocks(text: str) -> list[FileEdit]:
    """Extract every BEGIN_FILE/END_FILE block from model output."""
    pattern = re.compile(r'BEGIN_FILE[ \t]+(\S+)[ \t]*\n(.*?)END_FILE', re.DOTALL)
    return [
        FileEdit(path=m.group(1).strip().strip('`'), content=textwrap.dedent(m.group(2)))
        for m in pattern.finditer(text)
    ]


def validate_edits(edits: list[FileEdit], allow_list: list[str]) -> list[str]:
    """Return violation messages for any edit outside allow_list."""
    allow_set = set(allow_list)
    return [
        f"Edit to non-allowed file: {e.path!r} (allowed: {allow_list})"
        for e in edits
        if e.path not in allow_set
    ]
