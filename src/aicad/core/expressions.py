"""Closed-grammar validation for FreeCAD expression bindings.

A master-parameter expression may reference dotted identifiers
(``Params.width``), numeric literals and basic arithmetic. Function calls,
strings, brackets and every other construct are rejected before the text
reaches FreeCAD's expression engine, so a binding can never smuggle code.
"""

from __future__ import annotations

import re


MAX_EXPRESSION_LENGTH = 128

_TOKEN_PATTERN = re.compile(
    r"\s*(?:"
    r"(?P<identifier>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)"
    r"|(?P<number>\d+(?:\.\d+)?)"
    r"|(?P<operator>[+\-*/])"
    r"|(?P<open>\()"
    r"|(?P<close>\))"
    r")"
)


def validate_expression(expression: str) -> str:
    """Return the trimmed expression or raise ValueError for anything unsafe."""

    if not isinstance(expression, str):
        raise ValueError("The binding expression must be a string.")
    trimmed = expression.strip()
    if not trimmed:
        raise ValueError("The binding expression must not be empty.")
    if len(trimmed) > MAX_EXPRESSION_LENGTH:
        raise ValueError(
            f"The binding expression exceeds {MAX_EXPRESSION_LENGTH} characters."
        )

    position = 0
    depth = 0
    previous = "start"
    has_identifier = False
    while position < len(trimmed):
        match = _TOKEN_PATTERN.match(trimmed, position)
        if match is None or match.end() == position:
            raise ValueError(
                "The binding expression may only contain parameter names, "
                "numbers, + - * / and parentheses."
            )
        kind = str(match.lastgroup)
        if kind == "identifier":
            if previous in {"identifier", "number", "close"}:
                raise ValueError("The binding expression is malformed.")
            has_identifier = True
        elif kind == "number":
            if previous in {"identifier", "number", "close"}:
                raise ValueError("The binding expression is malformed.")
        elif kind == "operator":
            if previous in {"operator", "start", "open"} and match.group(
                "operator"
            ) not in {"+", "-"}:
                raise ValueError("The binding expression is malformed.")
        elif kind == "open":
            # An identifier followed by "(" would be a function call.
            if previous in {"identifier", "number", "close"}:
                raise ValueError(
                    "The binding expression must not contain function calls."
                )
            depth += 1
        elif kind == "close":
            if previous in {"operator", "open", "start"}:
                raise ValueError("The binding expression is malformed.")
            depth -= 1
            if depth < 0:
                raise ValueError("The binding expression has unbalanced parentheses.")
        previous = kind
        position = match.end()

    if depth != 0:
        raise ValueError("The binding expression has unbalanced parentheses.")
    if previous in {"operator", "open", "start"}:
        raise ValueError("The binding expression is malformed.")
    if not has_identifier:
        raise ValueError(
            "The binding expression must reference at least one parameter."
        )
    return trimmed
