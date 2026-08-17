"""Structured validation diagnostics."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    source: str
    blocking: bool

    def to_data(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source,
            "blocking": self.blocking,
        }


class ManifestValidationError(ValueError):
    def __init__(self, diagnostics: tuple[Diagnostic, ...]):
        self.diagnostics = diagnostics
        detail = "; ".join(
            f"{item.source}: {item.message}" for item in diagnostics if item.blocking
        )
        super().__init__(detail or "Manifest validation failed")
