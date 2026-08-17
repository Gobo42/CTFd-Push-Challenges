#!/usr/bin/env python3
"""Generate a fresh macro-free Push Challenges workbook."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from authoring.workbook import create_workbook


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--rows", type=int, default=500)
    arguments = parser.parse_args(argv)
    create_workbook(arguments.output, author_rows=arguments.rows)
    print(f"Created {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
