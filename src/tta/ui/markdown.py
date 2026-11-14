"""A small Markdown renderer for the assumptions page (SPEC section 14).

Scores on the 15% "clear visibility of assumptions": `docs/ASSUMPTIONS.md` is shown on the site as written.
The project declares no Markdown library, and the document is a file like any other: it is rendered as data.
Every character of it is escaped; only the structure below becomes markup, and only an `http(s)` address
becomes a link. Supported: headings, paragraphs, bullet and numbered lists (nested by indentation), pipe
tables, fenced code, block quotes, rules, and inline code, bold, italic and links.
"""

from __future__ import annotations

import re
from html import escape

FENCE = "```"
MAX_HEADING_LEVEL = 6
LINK_SCHEMES = ("https://", "http://")
LINK_REL = "noopener noreferrer"

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_ITEM = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TABLE_ROW = re.compile(r"^\s*\|.*$")
_TABLE_RULE = re.compile(r"^\s*\|\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_CELL_BREAK = re.compile(r"(?<!\\)\|")
_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)([^*]+?)(?<!\s)\*(?![*\w])")


def _emphasis(raw: str) -> str:
    """Escape the text, then turn `**bold**` and `*italic*` into markup."""
    escaped = escape(raw, quote=True)
    return _ITALIC.sub(r"<em>\1</em>", _BOLD.sub(r"<strong>\1</strong>", escaped))


def _link(label: str, target: str) -> str:
    """A link only for a web address; anything else (a script address, a file of the repository) stays text."""
    if not target.lower().startswith(LINK_SCHEMES):
        return _emphasis(label)
    return f'<a href="{escape(target, quote=True)}" rel="{LINK_REL}">{_emphasis(label)}</a>'


def _text(raw: str) -> str:
    parts: list[str] = []
    position = 0
    for match in _LINK.finditer(raw):
        parts.append(_emphasis(raw[position:match.start()]))
        parts.append(_link(match.group(1), match.group(2)))
        position = match.end()
    parts.append(_emphasis(raw[position:]))
    return "".join(parts)


def _inline(raw: str) -> str:
    """Inline code first, so that nothing inside it is read as emphasis or as a link."""
    parts: list[str] = []
    position = 0
    for match in _CODE.finditer(raw):
        parts.append(_text(raw[position:match.start()]))
        parts.append(f"<code>{escape(match.group(1), quote=True)}</code>")
        position = match.end()
    parts.append(_text(raw[position:]))
    return "".join(parts)


def _cells(row: str) -> list[str]:
    inner = row.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [cell.strip().replace("\\|", "|") for cell in _CELL_BREAK.split(inner)]


def _is_table_start(lines: list[str], index: int) -> bool:
    following = lines[index + 1] if index + 1 < len(lines) else ""
    return bool(_TABLE_ROW.match(lines[index]) and _TABLE_RULE.match(following))


def _table(lines: list[str], start: int) -> tuple[str, int]:
    head = "".join(f"<th>{_inline(cell)}</th>" for cell in _cells(lines[start]))
    index = start + 2
    rows: list[str] = []
    while index < len(lines) and _TABLE_ROW.match(lines[index]):
        rows.append("<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in _cells(lines[index])) + "</tr>")
        index += 1
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>", index


def _fence(lines: list[str], start: int) -> tuple[str, int]:
    index = start + 1
    body: list[str] = []
    while index < len(lines) and not lines[index].strip().startswith(FENCE):
        body.append(lines[index])
        index += 1
    return f"<pre><code>{escape(chr(10).join(body), quote=True)}</code></pre>", index + 1


def _is_ordered(marker: str) -> bool:
    return marker[0].isdigit()


def _list(lines: list[str], start: int) -> tuple[str, int]:
    """A list and the lists nested under its items by indentation. A blank line ends it."""
    first = _ITEM.match(lines[start])
    assert first is not None  # the caller checked
    base, ordered = len(first.group(1)), _is_ordered(first.group(2))
    items: list[tuple[str, str]] = []  # the item's text and the markup of what is nested under it
    index = start
    while index < len(lines) and lines[index].strip():
        match = _ITEM.match(lines[index])
        if match is None:
            if not (lines[index].startswith(" ") and items):
                break
            items[-1] = (f"{items[-1][0]} {lines[index].strip()}", items[-1][1])  # a wrapped item
            index += 1
        elif len(match.group(1)) > base + 1 and items:
            nested, index = _list(lines, index)
            items[-1] = (items[-1][0], items[-1][1] + nested)
        elif len(match.group(1)) < base or _is_ordered(match.group(2)) != ordered:
            break  # an outer list goes on, or a list of the other kind starts
        else:
            items.append((match.group(3), ""))
            index += 1
    tag = "ol" if ordered else "ul"
    body = "".join(f"<li>{_inline(text)}{nested}</li>" for text, nested in items)
    return f"<{tag}>{body}</{tag}>", index


def _quote(lines: list[str], start: int) -> tuple[str, int]:
    index = start
    quoted: list[str] = []
    while index < len(lines) and lines[index].lstrip().startswith(">"):
        quoted.append(lines[index].lstrip()[1:].strip())
        index += 1
    return f"<blockquote><p>{_inline(' '.join(part for part in quoted if part))}</p></blockquote>", index


def _starts_a_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    return bool(
        line.strip().startswith(FENCE) or _HEADING.match(line) or _RULE.match(line) or _ITEM.match(line)
        or line.lstrip().startswith(">") or _is_table_start(lines, index)
    )


def _paragraph(lines: list[str], start: int) -> tuple[str, int]:
    index = start + 1
    while index < len(lines) and lines[index].strip() and not _starts_a_block(lines, index):
        index += 1
    joined = " ".join(line.strip() for line in lines[start:index])
    return f"<p>{_inline(joined)}</p>", index


def _block(lines: list[str], index: int) -> tuple[str, int]:
    line = lines[index]
    if line.strip().startswith(FENCE):
        return _fence(lines, index)
    heading = _HEADING.match(line)
    if heading is not None:
        level = min(len(heading.group(1)), MAX_HEADING_LEVEL)
        return f"<h{level}>{_inline(heading.group(2))}</h{level}>", index + 1
    if _RULE.match(line):
        return "<hr>", index + 1
    if _is_table_start(lines, index):
        return _table(lines, index)
    if line.lstrip().startswith(">"):
        return _quote(lines, index)
    if _ITEM.match(line):
        return _list(lines, index)
    return _paragraph(lines, index)


def render(document: str) -> str:
    """The document as HTML. Safe to place in a page as it is: every character of the input was escaped."""
    lines = document.replace("\r\n", "\n").expandtabs(4).split("\n")
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        block, index = _block(lines, index)
        blocks.append(block)
    return "\n".join(blocks)
