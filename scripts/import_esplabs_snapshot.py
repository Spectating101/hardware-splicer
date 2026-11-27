"""Refresh HS's pinned snapshot of the esp-labs lessons (MIT, agharsallah/esp-labs-web).

    python scripts/import_esplabs_snapshot.py <esp-labs-web source dir> <40-hex commit>

The lessons are TypeScript files holding plain object literals. They are read as data by a small literal parser, never
executed: strings, numbers, true/false/null, arrays, objects, trailing commas, `as const`, `satisfies T`, spreads and names
of constants defined earlier in the same file. Anything else stops the import with the file and position. The output is the
lessons and kit as esp-labs wrote them, with esp-labs' licence and the commit.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parents[1] / "src/hardware_splicer/data/third_party/esp_labs"
TOKEN = re.compile(r"""\s*(?:(//[^\n]*)|(/\*.*?\*/)|("(?:\\.|[^"\\])*")|('(?:\\.|[^'\\])*')|(`(?:\\.|[^`\\$])*`)|(\.\.\.)|([{}\[\]:,])|(-?\d+(?:\.\d+)?)|([A-Za-z_$][\w$]*))""", re.S)


class LiteralError(ValueError):
    pass


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}


def _unescape(body: str) -> str:
    """A JavaScript string body to its value: \\n, \\uXXXX, \\u{...}, \\xXX, and any other escaped character as itself."""
    out, i = [], 0
    while i < len(body):
        ch = body[i]
        if ch != "\\" or i + 1 == len(body):
            out.append(ch)
            i += 1
            continue
        nxt = body[i + 1]
        if nxt == "u" and body[i + 2:i + 3] == "{":
            end = body.index("}", i)
            out.append(chr(int(body[i + 3:end], 16)))
            i = end + 1
        elif nxt == "u":
            out.append(chr(int(body[i + 2:i + 6], 16)))
            i += 6
        elif nxt == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
        elif nxt == "\n":
            i += 2  # a line continuation
        else:
            out.append(_ESCAPES.get(nxt, nxt))
            i += 2
    return "".join(out)


def _tokens(text: str) -> list[tuple[str, str]]:
    out, pos = [], 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        m = TOKEN.match(text, pos)
        if not m:
            raise LiteralError(f"unexpected text at {pos}: {text[pos:pos + 40]!r}")
        pos = m.end()
        comment, block, dq, sq, tpl, spread, punct, num, ident = m.groups()
        if comment or block:
            continue
        if dq or sq:
            out.append(("str", _unescape((dq or sq)[1:-1])))
        elif tpl:
            out.append(("str", _unescape(tpl[1:-1])))
        elif spread:
            out.append(("spread", spread))
        elif punct:
            out.append(("p", punct))
        elif num:
            out.append(("num", num))
        else:
            out.append(("id", ident))
    return out


class _Parser:
    def __init__(self, tokens: list[tuple[str, str]], env: dict[str, Any]):
        self.t, self.i, self.env = tokens, 0, env

    def peek(self) -> tuple[str, str] | None:
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self, kind: str, value: str | None = None) -> str:
        tok = self.peek()
        if tok is None or tok[0] != kind or (value is not None and tok[1] != value):
            raise LiteralError(f"expected {value or kind}, found {tok}")
        self.i += 1
        return tok[1]

    def value(self) -> Any:
        tok = self.peek()
        if tok is None:
            raise LiteralError("unexpected end")
        kind, text = tok
        if (kind, text) == ("p", "{"):
            return self.obj()
        if (kind, text) == ("p", "["):
            return self.arr()
        self.i += 1
        if kind == "str":
            return text
        if kind == "num":
            return float(text) if "." in text else int(text)
        if kind == "id":
            if text in ("true", "false", "null"):
                return {"true": True, "false": False, "null": None}[text]
            if text in self.env:
                return self.env[text]
        raise LiteralError(f"not a literal: {text!r}")

    def obj(self) -> dict[str, Any]:
        self.take("p", "{")
        out: dict[str, Any] = {}
        while self.peek() != ("p", "}"):
            if self.peek() and self.peek()[0] == "spread":
                self.i += 1
                out.update(self.value())
            else:
                key_kind, key = self.peek()
                if key_kind not in ("id", "str", "num"):
                    raise LiteralError(f"bad key {key!r}")
                self.i += 1
                if self.peek() == ("p", ":"):
                    self.i += 1
                    out[key] = self.value()
                else:  # shorthand {name}
                    out[key] = self.env[key]
            if self.peek() == ("p", ","):
                self.i += 1
        self.take("p", "}")
        return out

    def arr(self) -> list[Any]:
        self.take("p", "[")
        out: list[Any] = []
        while self.peek() != ("p", "]"):
            if self.peek() and self.peek()[0] == "spread":
                self.i += 1
                out.extend(self.value())
            else:
                out.append(self.value())
            if self.peek() == ("p", ","):
                self.i += 1
        self.take("p", "]")
        return out


def constants(source: str) -> dict[str, Any]:
    """Every `const NAME = <literal>` in a file, in order, so later ones may name earlier ones."""
    env: dict[str, Any] = {}
    for m in re.finditer(r"^(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]+)?=\s*", source, re.M):
        start = m.end()
        if source[start] not in "[{":
            continue  # a function or call, not data
        depth, i, quote = 0, start, None
        while i < len(source):
            ch = source[i]
            if quote:
                if ch == "\\":
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
            elif ch in "[{":
                depth += 1
            elif ch in "]}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        literal = source[start:i + 1]
        env[m.group(1)] = _Parser(_tokens(literal), env).value()
    return env


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", argv[1]):
        print("usage: import_esplabs_snapshot.py <esp-labs-web source dir> <40-hex commit>", file=sys.stderr)
        return 2
    src, commit = Path(argv[0]), argv[1]
    content = src / "src" / "content"
    lessons: dict[str, Any] = {}
    for path in sorted((content / "lessons").rglob("*.ts")):
        if path.name.endswith(".test.ts") or path.name == "index.ts":  # index files only list imported lessons
            continue
        try:
            env = constants(path.read_text(encoding="utf-8"))
        except LiteralError as exc:
            raise SystemExit(f"{path}: {exc}") from None
        for value in env.values():
            for item in value if isinstance(value, list) else [value]:
                if isinstance(item, dict) and item.get("kind") == "lesson" and "id" in item:
                    lessons[item["id"]] = item
    kit = constants((content / "kit.ts").read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "LICENSE", OUT / "LICENSE")
    (OUT / "lessons.json").write_text(json.dumps(lessons, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "kit.json").write_text(json.dumps({"items": kit["KIT_ITEMS"], "lesson_kit": kit["LESSON_KIT"]}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (OUT / "SNAPSHOT.json").write_text(json.dumps({
        "source": "https://github.com/agharsallah/esp-labs-web", "commit": commit, "license": "MIT (see LICENSE in this folder)",
        "counts": {"lessons": len(lessons)}, "board": "ESP32-S3-DevKitC-1 (N16R8), as the lessons state",
        "note": "esp-labs' lesson data, unchanged. Its status field is esp-labs' own report, not something HS observed.",
    }, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"lessons": len(lessons), "ids": sorted(lessons)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
