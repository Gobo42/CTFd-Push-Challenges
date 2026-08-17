"""Reference graph checks and authoring hint ordinal resolution."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypeAlias

from .errors import Diagnostic
from .model import HintSpec

RequiredHintInput: TypeAlias = str | Sequence[int]


@dataclass(frozen=True)
class RawHint:
    title: str
    content: str
    cost: int
    required_hints: RequiredHintInput
    source: str = ""


def find_cycle(
    edges: Mapping[str, str | None],
) -> tuple[str, ...] | None:
    """Return the first closed cycle path in mapping insertion order."""
    complete: set[str] = set()
    for start in edges:
        if start in complete:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current: str | None = start
        while current is not None and current in edges and current not in complete:
            if current in positions:
                beginning = positions[current]
                return tuple((*path[beginning:], current))
            positions[current] = len(path)
            path.append(current)
            current = edges[current]
        complete.update(path)
    return None


def _parse_ordinals(value: RequiredHintInput) -> tuple[int, ...] | None:
    if isinstance(value, str):
        if not value.strip():
            return ()
        tokens = tuple(token.strip() for token in value.split(","))
        if any(not token.isascii() or not token.isdecimal() for token in tokens):
            return None
        ordinals = tuple(int(token) for token in tokens)
    elif isinstance(value, Sequence):
        if any(type(item) is not int for item in value):
            return None
        ordinals = tuple(value)
    else:
        return None
    if any(ordinal <= 0 for ordinal in ordinals):
        return None
    return ordinals


def resolve_hint_ordinals(
    challenge: str,
    hints: Sequence[RawHint],
) -> tuple[tuple[HintSpec, ...], tuple[Diagnostic, ...]]:
    resolved: list[HintSpec] = []
    diagnostics: list[Diagnostic] = []
    for index, hint in enumerate(hints):
        ordinals = _parse_ordinals(hint.required_hints)
        current_ordinal = index + 1
        valid = (
            ordinals is not None
            and len(set(ordinals)) == len(ordinals)
            and all(ordinal < current_ordinal for ordinal in ordinals)
        )
        if valid:
            required_titles = tuple(hints[ordinal - 1].title for ordinal in ordinals)
        else:
            required_titles = ()
            diagnostics.append(
                Diagnostic(
                    code="hint_requirements_ignored",
                    message=(
                        f"{challenge!r} hint {current_ordinal} has invalid Required "
                        "Hints; its requirement was ignored"
                    ),
                    source=hint.source
                    or f"{challenge} hint {current_ordinal} Required Hints",
                    blocking=False,
                )
            )
        resolved.append(
            HintSpec(
                title=hint.title,
                content=hint.content,
                cost=hint.cost,
                required_hints=required_titles,
            )
        )
    return tuple(resolved), tuple(diagnostics)
