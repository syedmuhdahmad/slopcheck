"""Minimal Python syntax highlighter (Catppuccin Mocha colours) for the demo recording.

The VHS image has no bat/pygments, so demo.tape uses this as `cat`. Stdlib only.
"""

import io
import keyword
import sys
import tokenize

RESET = "\033[0m"


def rgb(hex_colour: str, italic: bool = False) -> str:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return f"\033[{'3;' if italic else ''}38;2;{r};{g};{b}m"


KEYWORD = rgb("#cba6f7")
FUNCTION = rgb("#89b4fa")
STRING = rgb("#a6e3a1")
COMMENT = rgb("#7f849c", italic=True)
NUMBER = rgb("#fab387")
TYPE = rgb("#f9e2af")
BUILTINS = {"str", "int", "dict", "list", "bool", "float", "None", "True", "False"}


def highlight(source: str) -> str:
    # Absolute offset of each line start, so whitespace between tokens is copied verbatim.
    starts = [0]
    for line in source.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))

    def offset(row: int, col: int) -> int:
        return starts[row - 1] + col if row - 1 < len(starts) else len(source)

    out: list[str] = []
    pos, prev = 0, ""
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        begin, end = offset(*tok.start), offset(*tok.end)
        out.append(source[pos:begin])
        text = source[begin:end]
        if tok.type == tokenize.COMMENT:
            colour = COMMENT
        elif tok.type == tokenize.STRING:
            colour = STRING
        elif tok.type == tokenize.NUMBER:
            colour = NUMBER
        elif tok.type == tokenize.NAME and text in BUILTINS:
            colour = TYPE
        elif tok.type == tokenize.NAME and keyword.iskeyword(text):
            colour = KEYWORD
        elif tok.type == tokenize.NAME and prev in ("def", "class"):
            colour = FUNCTION
        else:
            colour = ""
        out.append(f"{colour}{text}{RESET}" if colour and text.strip() else text)
        if tok.type == tokenize.NAME:
            prev = text
        pos = max(pos, end)
    out.append(source[pos:])
    return "".join(out)


if __name__ == "__main__":
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            sys.stdout.write(highlight(f.read()))
