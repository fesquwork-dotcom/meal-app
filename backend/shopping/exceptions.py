"""Domain errors for basket engine."""

from __future__ import annotations


class BasketBuildError(Exception):
    def __init__(self, message: str, code: str = "BASKET_BUILD_ERROR") -> None:
        super().__init__(message)
        self.code = code


class BasketPriceUnavailableError(BasketBuildError):
    def __init__(self, unresolved: list[str]) -> None:
        super().__init__(
            f"Price unavailable for {len(unresolved)} basket item(s)",
            code="BASKET_PRICE_UNAVAILABLE",
        )
        self.unresolved = unresolved
