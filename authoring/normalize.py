"""Convert authoring rows into the canonical manifest."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from push_challenges_core.errors import Diagnostic
from push_challenges_core.graph import RawHint, find_cycle, resolve_hint_ordinals
from push_challenges_core.manifest import validate_manifest_data
from push_challenges_core.model import Manifest
from push_challenges_core.tags import TagParseError, parse_hash_tags


@dataclass(frozen=True)
class AuthoringRow:
    source: str
    values: Mapping[str, object]


@dataclass(frozen=True)
class AuthoringDocument:
    rows: tuple[AuthoringRow, ...]
    diagnostics: tuple[Diagnostic, ...]


@dataclass(frozen=True)
class ValidationResult:
    manifest: Manifest | None
    diagnostics: tuple[Diagnostic, ...]


STATE_VALUES = {
    "": "hidden",
    "Hidden": "hidden",
    "Visible": "visible",
    "Locked": "locked",
    "hidden": "hidden",
    "visible": "visible",
    "locked": "locked",
}
TYPE_VALUES = {
    "Standard": "standard",
    "Dynamic": "dynamic",
    "standard": "standard",
    "dynamic": "dynamic",
}
LOGIC_VALUES = {
    "": "any",
    "Require Any Flag": "any",
    "Require All Flags": "all",
    "any": "any",
    "all": "all",
}
SOLUTION_STATE_VALUES = {
    "": "hidden",
    "Hidden": "hidden",
    "Visible": "visible",
    "Solved": "solved",
    "hidden": "hidden",
    "visible": "visible",
    "solved": "solved",
}


def _text(value: object) -> str:
    return "" if value is None else str(value)


def _source(row: AuthoringRow, column: str) -> str:
    return f"{row.source} {column}"


def _enum_value(
    row: AuthoringRow,
    column: str,
    choices: Mapping[str, str],
    diagnostics: list[Diagnostic],
) -> str:
    raw = _text(row.values.get(column)).strip()
    if raw in choices:
        return choices[raw]
    diagnostics.append(
        Diagnostic(
            "invalid_authoring_value",
            f"Unexpected {column} value {raw!r}",
            _source(row, column),
            True,
        )
    )
    return raw


def _integer_value(
    row: AuthoringRow,
    column: str,
    diagnostics: list[Diagnostic],
    *,
    default: int = 0,
) -> int:
    raw = row.values.get(column)
    if type(raw) is int:
        return raw
    text = _text(raw).strip()
    try:
        if not text or any(character in text for character in ".eE"):
            raise ValueError
        return int(text, 10)
    except ValueError:
        diagnostics.append(
            Diagnostic(
                "invalid_integer",
                f"{column} must be a whole number",
                _source(row, column),
                True,
            )
        )
        return default


def _json_array(
    row: AuthoringRow,
    column: str,
    diagnostics: list[Diagnostic],
) -> list[object]:
    raw = row.values.get(column)
    if isinstance(raw, list):
        return raw
    text = _text(raw).strip()
    if not text:
        return []
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        diagnostics.append(
            Diagnostic(
                f"invalid_{column.lower()}_json",
                f"{column} is not valid JSON: {error.msg}",
                _source(row, column),
                True,
            )
        )
        return []
    if not isinstance(value, list):
        diagnostics.append(
            Diagnostic(
                f"invalid_{column.lower()}_json",
                f"{column} must contain a JSON array",
                _source(row, column),
                True,
            )
        )
        return []
    return value


def _solution_data(
    row: AuthoringRow, diagnostics: list[Diagnostic]
) -> dict[str, object]:
    content = _text(row.values.get("Solution"))
    if not content:
        return {"action": "preserve", "content": None, "state": None}
    if content == "REMOVE":
        return {"action": "clear", "content": None, "state": None}
    state = _enum_value(
        row,
        "Solution State",
        SOLUTION_STATE_VALUES,
        diagnostics,
    )
    return {"action": "upsert", "content": content, "state": state}


def _flags_data(
    row: AuthoringRow, diagnostics: list[Diagnostic]
) -> list[object]:
    values = _json_array(row, "Flags", diagnostics)
    result: list[object] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            diagnostics.append(
                Diagnostic(
                    "invalid_flag",
                    "Each flag must be an object",
                    f"{_source(row, 'Flags')}[{index}]",
                    True,
                )
            )
            continue
        result.append(value)
    return result


def _hints_data(
    row: AuthoringRow, diagnostics: list[Diagnostic]
) -> list[dict[str, object]]:
    values = _json_array(row, "Hints", diagnostics)
    raw_hints: list[RawHint] = []
    for index, value in enumerate(values):
        item_source = f"{_source(row, 'Hints')}[{index}]"
        if not isinstance(value, dict):
            diagnostics.append(
                Diagnostic(
                    "invalid_hint",
                    "Each hint must be an object",
                    item_source,
                    True,
                )
            )
            continue
        expected = {"title", "content", "cost", "required_hints"}
        if set(value) != expected:
            diagnostics.append(
                Diagnostic(
                    "invalid_hint",
                    "Hint properties must be title, content, cost, required_hints",
                    item_source,
                    True,
                )
            )
            continue
        cost = value.get("cost")
        if type(cost) is not int:
            diagnostics.append(
                Diagnostic(
                    "invalid_hint",
                    "Hint cost must be a whole number",
                    f"{item_source}.cost",
                    True,
                )
            )
            cost = 0
        required = value.get("required_hints")
        if not isinstance(required, (str, Sequence)):
            required = ()
        raw_hints.append(
            RawHint(
                title=_text(value.get("title")),
                content=_text(value.get("content")),
                cost=cost,
                required_hints=required,
                source=f"{item_source}.required_hints",
            )
        )
    challenge = _text(row.values.get("Name"))
    hints, hint_diagnostics = resolve_hint_ordinals(challenge, raw_hints)
    diagnostics.extend(hint_diagnostics)
    return [
        {
            "title": hint.title,
            "content": hint.content,
            "cost": hint.cost,
            "required_hints": list(hint.required_hints),
        }
        for hint in hints
    ]


def _challenge_data(
    row: AuthoringRow, diagnostics: list[Diagnostic]
) -> dict[str, object]:
    try:
        tags = parse_hash_tags(_text(row.values.get("Tags")), _source(row, "Tags"))
    except TagParseError as error:
        diagnostics.append(
            Diagnostic("invalid_tags", str(error), _source(row, "Tags"), True)
        )
        tags = ()
    next_name = _text(row.values.get("Next")).strip() or None
    return {
        "name": _text(row.values.get("Name")),
        "description": _text(row.values.get("Description")),
        "value": _integer_value(row, "Value", diagnostics),
        "category": _text(row.values.get("Category")),
        "state": _enum_value(row, "State", STATE_VALUES, diagnostics),
        "type": _enum_value(row, "Type", TYPE_VALUES, diagnostics),
        "logic": _enum_value(row, "Logic", LOGIC_VALUES, diagnostics),
        "max_attempts": _integer_value(row, "Max Attempts", diagnostics),
        "attribution": _text(row.values.get("Attribution")),
        "connection_info": _text(row.values.get("Connection Info")),
        "tags": list(tags),
        "next": next_name,
        "solution": _solution_data(row, diagnostics),
        "flags": _flags_data(row, diagnostics),
        "hints": _hints_data(row, diagnostics),
    }


def normalize(document: AuthoringDocument) -> ValidationResult:
    diagnostics = list(document.diagnostics)
    challenges = [
        _challenge_data(row, diagnostics) for row in document.rows
    ]
    names = {
        challenge["name"]
        for challenge in challenges
        if isinstance(challenge["name"], str) and challenge["name"]
    }
    local_edges = {
        challenge["name"]: (
            challenge["next"] if challenge["next"] in names else None
        )
        for challenge in challenges
        if challenge["name"] in names
    }
    cycle = find_cycle(local_edges)
    if cycle is not None:
        diagnostics.append(
            Diagnostic(
                "circular_next_chain",
                "Circular Next chain: " + " -> ".join(cycle),
                "Next",
                True,
            )
        )

    data = {
        "format": "push-challenges",
        "version": 1,
        "warnings": [],
        "challenges": challenges,
    }
    manifest, manifest_diagnostics = validate_manifest_data(data)
    diagnostics.extend(manifest_diagnostics)
    result_diagnostics = tuple(diagnostics)
    if manifest is None or any(item.blocking for item in result_diagnostics):
        return ValidationResult(None, result_diagnostics)
    warnings = tuple(item for item in result_diagnostics if not item.blocking)
    return ValidationResult(replace(manifest, warnings=warnings), result_diagnostics)
