"""Request/response models for the interferometry workbench API.

All numeric inputs must be *finite decimal numbers* (JSON numbers or decimal
strings such as ``"0.25"``, ``"1e-3"``).  They are parsed into exact
``fractions.Fraction`` values; anything else (``"1/3"``, ``"nan"``, ``"inf"``,
non-numeric text) is rejected with a 422 validation error.
"""

from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, WithJsonSchema, model_validator
from pydantic.functional_validators import BeforeValidator

_DECIMAL_RE = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")


def parse_finite_decimal(value) -> Fraction:
    """Parse a finite decimal number into an exact ``Fraction``."""
    if isinstance(value, bool):
        raise ValueError("expected a finite decimal number, got a boolean")
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("expected a finite decimal number, got a non-finite value")
        # str(float) round-trips to the shortest decimal the user typed.
        return Fraction(Decimal(str(value)))
    if isinstance(value, str):
        text = value.strip()
        if not _DECIMAL_RE.match(text):
            raise ValueError(f"{value!r} is not a finite decimal number")
        try:
            return Fraction(Decimal(text))
        except InvalidOperation as exc:  # pragma: no cover - regex already guards
            raise ValueError(f"{value!r} is not a finite decimal number") from exc
    raise ValueError(f"expected a finite decimal number, got {type(value).__name__}")


FiniteDecimal = Annotated[
    Fraction,
    BeforeValidator(parse_finite_decimal),
    WithJsonSchema(
        {
            "type": "string",
            "pattern": r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$",
            "description": "Finite decimal number (JSON number or decimal string).",
            "examples": ["0.25", "632.8e-9", "3"],
        }
    ),
]


class RangeInput(BaseModel):
    """Closed distance interval [lo, hi]."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    lo: FiniteDecimal
    hi: FiniteDecimal

    @model_validator(mode="after")
    def _check_order(self) -> "RangeInput":
        if self.lo > self.hi:
            raise ValueError("range lower endpoint must not exceed the upper endpoint")
        return self


class ChannelInput(BaseModel):
    """One interferometer channel: wavelength λ, wrapped phase p, error bound ε."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    wavelength: FiniteDecimal
    phase: FiniteDecimal
    epsilon: FiniteDecimal

    @model_validator(mode="after")
    def _check_bounds(self) -> "ChannelInput":
        if self.wavelength <= 0:
            raise ValueError("wavelength must be positive")
        if not (0 <= self.phase < 1):
            raise ValueError("phase must satisfy 0 <= p < 1")
        if not (0 <= self.epsilon < Fraction(1, 4)):
            raise ValueError("error bound must satisfy 0 <= ε < 1/4 of a cycle")
        return self


class SolveInput(BaseModel):
    """Full solve request: distance range plus 2..32 channels."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    range: RangeInput
    channels: list[ChannelInput] = Field(min_length=2, max_length=32)
