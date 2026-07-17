from __future__ import annotations

import pytest

from aicad.core.expressions import MAX_EXPRESSION_LENGTH, validate_expression


def test_accepts_parameter_arithmetic() -> None:
    assert validate_expression("Params.width") == "Params.width"
    assert validate_expression(" Params.width / 2 + 5 ") == "Params.width / 2 + 5"
    assert (
        validate_expression("(Params.width - 2 * Params.wall) * 0.5")
        == "(Params.width - 2 * Params.wall) * 0.5"
    )
    assert validate_expression("-Params.offset") == "-Params.offset"


@pytest.mark.parametrize(
    "expression",
    [
        "",
        "   ",
        "42",  # no parameter reference
        "sin(Params.angle)",  # function call
        "Params.width(2)",  # call on identifier
        "__import__('os')",
        "Params.width; 1",
        "Params.width ** 2",
        "Params.width + ",
        "(Params.width",
        "Params.width)",
        "Params..width",
        "Params.width Params.height",
        "a" * (MAX_EXPRESSION_LENGTH + 1),
    ],
)
def test_rejects_unsafe_or_malformed_expressions(expression: str) -> None:
    with pytest.raises(ValueError):
        validate_expression(expression)


def test_rejects_non_string_values() -> None:
    with pytest.raises(ValueError):
        validate_expression(42)  # type: ignore[arg-type]
