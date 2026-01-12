"""Tiny S-expression parser for KiCad-style files (.kicad_pcb, .net).

KiCad uses an S-expression-like syntax with:
- parentheses for lists
- quoted strings (double quotes) that may contain spaces
- atoms (symbols / numbers)

This parser intentionally supports just what we need for extracting nets,
footprints, pads, segments, and simple metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, List


class SexpError(ValueError):
    pass


@dataclass(frozen=True)
class _Token:
    kind: str  # "(", ")", "atom", "str"
    value: str


def _tokenize(text: str) -> Iterator[_Token]:
    i = 0
    n = len(text)

    def peek(offset: int = 0) -> str:
        j = i + offset
        return text[j] if 0 <= j < n else ""

    while i < n:
        c = text[i]

        if c.isspace():
            i += 1
            continue

        # Line comments: ';' to EOL.
        if c == ";":
            while i < n and text[i] not in "\r\n":
                i += 1
            continue

        if c == "(":
            i += 1
            yield _Token("(", "(")
            continue
        if c == ")":
            i += 1
            yield _Token(")", ")")
            continue

        if c == '"':
            i += 1
            buf: List[str] = []
            while i < n:
                ch = text[i]
                if ch == "\\":
                    nxt = peek(1)
                    if not nxt:
                        raise SexpError("Dangling escape in string")
                    buf.append(nxt)
                    i += 2
                    continue
                if ch == '"':
                    i += 1
                    break
                buf.append(ch)
                i += 1
            else:
                raise SexpError("Unterminated string")

            yield _Token("str", "".join(buf))
            continue

        start = i
        while i < n and (not text[i].isspace()) and text[i] not in "()":
            i += 1
        yield _Token("atom", text[start:i])


def _atom_value(tok: _Token) -> Any:
    if tok.kind == "str":
        return tok.value

    v = tok.value
    try:
        if v.lower().startswith("0x"):
            return int(v, 16)
        if any(ch in v for ch in (".", "e", "E")):
            return float(v)
        return int(v)
    except ValueError:
        return v


def parse_sexp(text: str) -> Any:
    tokens = list(_tokenize(text))
    idx = 0

    def parse_one() -> Any:
        nonlocal idx
        if idx >= len(tokens):
            raise SexpError("Unexpected end of input")

        tok = tokens[idx]
        if tok.kind == "(":
            idx += 1
            out: List[Any] = []
            while True:
                if idx >= len(tokens):
                    raise SexpError("Unterminated list")
                if tokens[idx].kind == ")":
                    idx += 1
                    return out
                out.append(parse_one())

        if tok.kind == ")":
            raise SexpError("Unexpected ')'")

        idx += 1
        return _atom_value(tok)

    parsed = parse_one()
    if idx != len(tokens):
        raise SexpError("Trailing tokens after top-level expression")
    return parsed


def parse_sexp_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return parse_sexp(f.read())


def sexp_find_all(node: Any, head: str) -> List[list]:
    found: List[list] = []

    def walk(n: Any) -> None:
        if not isinstance(n, list):
            return
        if n and isinstance(n[0], str) and n[0] == head:
            found.append(n)
        for child in n:
            walk(child)

    walk(node)
    return found

