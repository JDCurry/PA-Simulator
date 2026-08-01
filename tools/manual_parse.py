"""Parse docs/USER_MANUAL.md into a structured block list.

The markdown file is the single source of truth: the in-app Manual page renders it
directly, and the Word and PDF builds both consume the structure this module emits.
Editing the manual updates all three.

Only the subset of markdown the manual actually uses is supported -- headings,
paragraphs, bullet and numbered lists, blockquote callouts, pipe tables, horizontal
rules, and inline bold / italic / code / links. Anything else passes through as text.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "docs" / "USER_MANUAL.md"

# Inline markup, matched longest-delimiter-first so ** wins over *.
_INLINE = re.compile(
    r"(?P<code>`[^`]+`)"
    r"|(?P<bold>\*\*[^*]+\*\*)"
    r"|(?P<italic>\*[^*]+\*)"
    r"|(?P<link>\[[^\]]+\]\([^)]+\))"
)


def parse_inline(text: str) -> list[dict[str, Any]]:
    """Split a string into styled runs: {text, bold, italic, code}."""
    runs: list[dict[str, Any]] = []
    pos = 0

    def push(s: str, **style) -> None:
        if s:
            runs.append({"text": s, "bold": False, "italic": False,
                         "code": False, **style})

    for m in _INLINE.finditer(text):
        push(text[pos:m.start()])
        if m.group("code"):
            push(m.group("code")[1:-1], code=True)
        elif m.group("bold"):
            push(m.group("bold")[2:-2], bold=True)
        elif m.group("italic"):
            push(m.group("italic")[1:-1], italic=True)
        elif m.group("link"):
            label, target = re.match(r"\[([^\]]+)\]\(([^)]+)\)", m.group("link")).groups()
            # In-document anchors become plain text in print; real URLs are kept
            # visible, because a printed page cannot be clicked.
            if target.startswith("#"):
                push(label)
            else:
                push(label)
                push(f" ({target})", italic=True)
        pos = m.end()
    push(text[pos:])
    return runs or [{"text": "", "bold": False, "italic": False, "code": False}]


def _split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_divider(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:|-]+\|?", line.strip())) and "-" in line


def _measure(cell: str) -> str:
    """Cell text as it will render, so markup characters do not inflate the width."""
    return re.sub(r"\*\*|\*|`", "", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cell))


def column_weights(header: list[str], rows: list[list[str]]) -> list[float]:
    """Relative column widths, normalized to sum to len(header).

    Weighted by the longest *unbreakable word* plus a damped measure of total
    content. Naive character-count weighting starves narrow columns: a "Blocking"
    header sitting beside a column of long sentences gets allocated less width than
    the word itself needs, and then overflows into its neighbour. The longest word is
    a hard floor on what the column must accommodate; the damped volume distributes
    what is left over according to how much text actually has to wrap.
    """
    n = len(header)
    spans: list[float] = []
    for i in range(n):
        cells = [_measure(header[i])] + [
            _measure(r[i]) for r in rows if i < len(r)
        ]
        longest_word = max(
            (len(w) for c in cells for w in c.split()), default=4
        )
        # Cap volume: past a point the text just wraps to more lines.
        volume = min(max((len(c) for c in cells), default=4), 70)
        spans.append(longest_word + 0.6 * volume)
    total = sum(spans) or 1.0
    return [round(s / total * n, 4) for s in spans]


def parse(md: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lines = md.splitlines()
    i = 0

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if not line:
            i += 1
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", line):
            blocks.append({"type": "rule"})
            i += 1
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            blocks.append({
                "type": "heading",
                "level": len(m.group(1)),
                "runs": parse_inline(m.group(2).strip()),
                "text": re.sub(r"[*`\[\]]|\([^)]*\)", "", m.group(2)).strip(),
            })
            i += 1
            continue

        # Table: a pipe row followed by a divider row
        if line.startswith("|") and i + 1 < len(lines) and _is_divider(lines[i + 1]):
            header = _split_row(line)
            i += 2
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = _split_row(lines[i])
                cells += [""] * (len(header) - len(cells))
                rows.append(cells[:len(header)])
                i += 1
            blocks.append({
                "type": "table",
                "header": [parse_inline(c) for c in header],
                "header_text": header,
                "rows": [[parse_inline(c) for c in r] for r in rows],
                "rows_text": rows,
                "weights": column_weights(header, rows),
            })
            continue

        # Blockquote callout, possibly several paragraphs
        if line.startswith(">"):
            paras: list[str] = []
            current: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                content = re.sub(r"^\s*>\s?", "", lines[i])
                if content.strip():
                    current.append(content.strip())
                else:
                    if current:
                        paras.append(" ".join(current))
                        current = []
                i += 1
            if current:
                paras.append(" ".join(current))
            blocks.append({
                "type": "callout",
                "paragraphs": [parse_inline(p) for p in paras],
            })
            continue

        # Lists -- bullet or numbered, each item possibly wrapped over lines
        bullet = re.match(r"^([-*+])\s+(.*)$", line)
        number = re.match(r"^(\d+)[.)]\s+(.*)$", line)
        if bullet or number:
            ordered = number is not None
            items: list[str] = []
            start = int(number.group(1)) if ordered else 1
            while i < len(lines):
                cur = lines[i]
                stripped = cur.strip()
                if not stripped:
                    # A blank line ends the list unless the next line continues it.
                    nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                    if not (re.match(r"^([-*+])\s+", nxt) or re.match(r"^\d+[.)]\s+", nxt)):
                        break
                    i += 1
                    continue
                b = re.match(r"^([-*+])\s+(.*)$", stripped)
                n = re.match(r"^(\d+)[.)]\s+(.*)$", stripped)
                if b and not ordered:
                    items.append(b.group(2))
                elif n and ordered:
                    items.append(n.group(2))
                elif (b or n):
                    break                       # list type switched
                elif cur.startswith((" ", "\t")) and items:
                    items[-1] += " " + stripped  # continuation of the previous item
                else:
                    break
                i += 1
            blocks.append({
                "type": "list",
                "ordered": ordered,
                "start": start,
                "items": [parse_inline(x) for x in items],
            })
            continue

        # Paragraph -- consume until a blank line or a block-level marker
        para: list[str] = []
        while i < len(lines):
            cur = lines[i].strip()
            if (not cur or cur.startswith(("#", ">", "|"))
                    or re.fullmatch(r"-{3,}", cur)
                    or re.match(r"^([-*+])\s+", cur)
                    or re.match(r"^\d+[.)]\s+", cur)):
                break
            para.append(cur)
            i += 1
        if para:
            blocks.append({"type": "paragraph", "runs": parse_inline(" ".join(para))})

    return blocks


def load_blocks(path: Path = MANUAL) -> list[dict[str, Any]]:
    return parse(path.read_text(encoding="utf-8"))


def document_title(blocks: list[dict[str, Any]]) -> str:
    for b in blocks:
        if b["type"] == "heading" and b["level"] == 1:
            return b["text"]
    return "User Manual"


if __name__ == "__main__":
    blocks = load_blocks()
    out = ROOT / "build" / "manual_blocks.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(blocks, indent=1), encoding="utf-8")

    counts: dict[str, int] = {}
    for b in blocks:
        counts[b["type"]] = counts.get(b["type"], 0) + 1
    print(f"{len(blocks)} blocks -> {out}")
    print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for b in blocks:
        if b["type"] == "table":
            print(f"  table {len(b['header_text'])} cols x {len(b['rows_text'])} rows: "
                  f"{b['header_text']}")
