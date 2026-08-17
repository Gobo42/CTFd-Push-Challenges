#!/usr/bin/env python3
"""Validate CSV/XLSX authoring input and optionally export a manifest."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authoring.csv_input import load_csv
from authoring.normalize import AuthoringDocument, normalize
from authoring.preview import render_preview
from push_challenges_core.errors import Diagnostic
from push_challenges_core.manifest import dump_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate challenge authoring input"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def _load(path: Path) -> AuthoringDocument:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".xlsx":
        try:
            from authoring.xlsx_input import load_xlsx
        except ImportError:
            return AuthoringDocument(
                (),
                (
                    Diagnostic(
                        "xlsx_support_unavailable",
                        "XLSX support requires the authoring tools and openpyxl",
                        str(path),
                        True,
                    ),
                ),
            )
        return load_xlsx(path)
    return AuthoringDocument(
        (),
        (
            Diagnostic(
                "unsupported_input",
                "Input must end in .csv or .xlsx",
                str(path),
                True,
            ),
        ),
    )


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    result = normalize(_load(arguments.input))
    sys.stdout.write(render_preview(result))
    if result.manifest is None:
        return 1
    if arguments.output is not None:
        dump_manifest(result.manifest, arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
