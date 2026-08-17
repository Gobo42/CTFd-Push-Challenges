"""Strict, Excel-compatible CSV input."""

from __future__ import annotations

import csv
from pathlib import Path

from push_challenges_core.errors import Diagnostic

from .normalize import AuthoringDocument, AuthoringRow

CSV_HEADERS = (
    "Name",
    "Description",
    "Value",
    "Category",
    "State",
    "Type",
    "Tags",
    "Next",
    "Logic",
    "Max Attempts",
    "Attribution",
    "Connection Info",
    "Solution",
    "Solution State",
    "Flags",
    "Hints",
)


def _header_error(actual: tuple[str, ...]) -> Diagnostic:
    duplicates = sorted({item for item in actual if actual.count(item) > 1})
    if duplicates:
        detail = f"duplicate header(s): {', '.join(duplicates)}"
    else:
        detail = (
            "expected exact headers in this order: " + ", ".join(CSV_HEADERS)
        )
    return Diagnostic("invalid_csv_headers", detail, "CSV row 1", True)


def load_csv(path: Path) -> AuthoringDocument:
    rows: list[AuthoringRow] = []
    diagnostics: list[Diagnostic] = []
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = tuple(next(reader, ()))
            if header != CSV_HEADERS:
                return AuthoringDocument((), (_header_error(header),))
            for line_number, values in enumerate(reader, start=2):
                if not values or all(not value.strip() for value in values):
                    continue
                if len(values) != len(CSV_HEADERS):
                    diagnostics.append(
                        Diagnostic(
                            "invalid_csv_row",
                            (
                                f"Expected {len(CSV_HEADERS)} columns, "
                                f"found {len(values)}"
                            ),
                            f"CSV row {line_number}",
                            True,
                        )
                    )
                    continue
                rows.append(
                    AuthoringRow(
                        source=f"CSV row {line_number}",
                        values=dict(zip(CSV_HEADERS, values, strict=True)),
                    )
                )
    except (OSError, UnicodeError, csv.Error) as error:
        diagnostics.append(
            Diagnostic("csv_read_failed", str(error), str(path), True)
        )
    return AuthoringDocument(tuple(rows), tuple(diagnostics))
