"""Strict loading, validation, and writing of canonical manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import Diagnostic, ManifestValidationError
from .model import ChallengeSpec, FlagSpec, HintSpec, Manifest, SolutionSpec

TOP_KEYS = {"format", "version", "warnings", "challenges"}
WARNING_KEYS = {"code", "message", "source", "blocking"}
CHALLENGE_KEYS = {
    "name",
    "description",
    "value",
    "category",
    "state",
    "type",
    "logic",
    "max_attempts",
    "attribution",
    "connection_info",
    "tags",
    "next",
    "solution",
    "flags",
    "hints",
}
FLAG_KEYS = {"type", "content", "data"}
HINT_KEYS = {"title", "content", "cost", "required_hints"}
SOLUTION_KEYS = {"action", "content", "state"}


def _error(
    diagnostics: list[Diagnostic],
    code: str,
    message: str,
    source: str,
    *,
    blocking: bool = True,
) -> None:
    diagnostics.append(Diagnostic(code, message, source, blocking))


def _check_keys(
    value: dict[str, Any],
    expected: set[str],
    source: str,
    diagnostics: list[Diagnostic],
) -> None:
    for key in sorted(set(value) - expected):
        _error(
            diagnostics,
            "unknown_property",
            f"Unknown property {key!r}",
            f"{source}.{key}" if source else key,
        )
    for key in sorted(expected - set(value)):
        _error(
            diagnostics,
            "missing_property",
            f"Required property {key!r} is missing",
            f"{source}.{key}" if source else key,
        )


def _string(
    value: object,
    source: str,
    diagnostics: list[Diagnostic],
    *,
    allow_empty: bool = True,
    maximum: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        _error(diagnostics, "invalid_type", "Expected a string", source)
        return None
    if not allow_empty and not value:
        _error(diagnostics, "empty_value", "Value may not be empty", source)
    if maximum is not None and len(value) > maximum:
        _error(
            diagnostics,
            "value_too_long",
            f"Value exceeds CTFd's {maximum}-character limit",
            source,
        )
    return value


def _integer(
    value: object,
    source: str,
    diagnostics: list[Diagnostic],
    *,
    minimum: int | None = None,
) -> int | None:
    if type(value) is not int:
        _error(diagnostics, "invalid_type", "Expected an integer", source)
        return None
    if minimum is not None and value < minimum:
        _error(
            diagnostics,
            "value_out_of_range",
            f"Value must be at least {minimum}",
            source,
        )
    return value


def _enum(
    value: object,
    choices: set[str],
    source: str,
    diagnostics: list[Diagnostic],
) -> str | None:
    parsed = _string(value, source, diagnostics)
    if parsed is not None and parsed not in choices:
        _error(
            diagnostics,
            "invalid_value",
            f"Expected one of {', '.join(sorted(choices))}",
            source,
        )
    return parsed


def _warning(
    value: object, index: int, diagnostics: list[Diagnostic]
) -> Diagnostic | None:
    source = f"warnings[{index}]"
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    _check_keys(value, WARNING_KEYS, source, diagnostics)
    code = _string(value.get("code"), f"{source}.code", diagnostics, allow_empty=False)
    message = _string(
        value.get("message"), f"{source}.message", diagnostics, allow_empty=False
    )
    item_source = _string(
        value.get("source"), f"{source}.source", diagnostics, allow_empty=False
    )
    blocking = value.get("blocking")
    if type(blocking) is not bool:
        _error(
            diagnostics,
            "invalid_type",
            "Expected a boolean",
            f"{source}.blocking",
        )
    elif blocking:
        _error(
            diagnostics,
            "invalid_warning",
            "Persisted authoring warnings must be non-blocking",
            f"{source}.blocking",
        )
    if (
        code is None
        or message is None
        or item_source is None
        or type(blocking) is not bool
    ):
        return None
    return Diagnostic(code, message, item_source, blocking)


def _flag(
    value: object, source: str, diagnostics: list[Diagnostic]
) -> FlagSpec | None:
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    _check_keys(value, FLAG_KEYS, source, diagnostics)
    flag_type = _enum(
        value.get("type"), {"static", "regex"}, f"{source}.type", diagnostics
    )
    content = _string(
        value.get("content"), f"{source}.content", diagnostics, allow_empty=False
    )
    data = _enum(
        value.get("data"),
        {"case_sensitive", "case_insensitive"},
        f"{source}.data",
        diagnostics,
    )
    if (
        flag_type not in {"static", "regex"}
        or content is None
        or data not in {"case_sensitive", "case_insensitive"}
    ):
        return None
    return FlagSpec(flag_type, content, data)


def _hint(
    value: object, source: str, diagnostics: list[Diagnostic]
) -> HintSpec | None:
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    _check_keys(value, HINT_KEYS, source, diagnostics)
    title = _string(
        value.get("title"),
        f"{source}.title",
        diagnostics,
        allow_empty=False,
        maximum=80,
    )
    content = _string(
        value.get("content"), f"{source}.content", diagnostics, allow_empty=False
    )
    cost = _integer(value.get("cost"), f"{source}.cost", diagnostics, minimum=0)
    raw_required = value.get("required_hints")
    required: list[str] = []
    if not isinstance(raw_required, list):
        _error(
            diagnostics,
            "invalid_type",
            "Expected an array",
            f"{source}.required_hints",
        )
    else:
        for index, item in enumerate(raw_required):
            parsed = _string(
                item,
                f"{source}.required_hints[{index}]",
                diagnostics,
                allow_empty=False,
                maximum=80,
            )
            if parsed is not None:
                if parsed in required:
                    _error(
                        diagnostics,
                        "duplicate_hint_requirement",
                        f"Duplicate required hint title {parsed!r}",
                        f"{source}.required_hints[{index}]",
                    )
                required.append(parsed)
    if title is not None and title in required:
        _error(
            diagnostics,
            "self_hint_requirement",
            "A hint cannot require itself",
            f"{source}.required_hints",
        )
    if title is None or content is None or cost is None:
        return None
    return HintSpec(title, content, cost, tuple(required))


def _solution(
    value: object, source: str, diagnostics: list[Diagnostic]
) -> SolutionSpec | None:
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    _check_keys(value, SOLUTION_KEYS, source, diagnostics)
    action = _enum(
        value.get("action"),
        {"preserve", "upsert", "clear"},
        f"{source}.action",
        diagnostics,
    )
    content = value.get("content")
    state = value.get("state")
    if action == "upsert":
        parsed_content = _string(
            content, f"{source}.content", diagnostics, allow_empty=False
        )
        parsed_state = _enum(
            state,
            {"hidden", "visible", "solved"},
            f"{source}.state",
            diagnostics,
        )
        if parsed_content is None or parsed_state not in {
            "hidden",
            "visible",
            "solved",
        }:
            return None
        return SolutionSpec("upsert", parsed_content, parsed_state)
    if action in {"preserve", "clear"}:
        if content is not None:
            _error(
                diagnostics,
                "invalid_solution_invariant",
                f"{action} solution content must be null",
                f"{source}.content",
            )
        if state is not None:
            _error(
                diagnostics,
                "invalid_solution_invariant",
                f"{action} solution state must be null",
                f"{source}.state",
            )
        return SolutionSpec(action)
    return None


def _challenge(
    value: object, index: int, diagnostics: list[Diagnostic]
) -> ChallengeSpec | None:
    source = f"challenges[{index}]"
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    _check_keys(value, CHALLENGE_KEYS, source, diagnostics)
    name = _string(
        value.get("name"),
        f"{source}.name",
        diagnostics,
        allow_empty=False,
        maximum=80,
    )
    description = _string(
        value.get("description"),
        f"{source}.description",
        diagnostics,
        maximum=65535,
    )
    challenge_value = _integer(value.get("value"), f"{source}.value", diagnostics)
    category = _string(
        value.get("category"),
        f"{source}.category",
        diagnostics,
        allow_empty=False,
        maximum=80,
    )
    state = _enum(
        value.get("state"),
        {"hidden", "visible", "locked"},
        f"{source}.state",
        diagnostics,
    )
    raw_type = value.get("type")
    challenge_type = _string(raw_type, f"{source}.type", diagnostics)
    if challenge_type == "dynamic":
        _error(
            diagnostics,
            "unsupported_challenge_type",
            "Dynamic is recognized but not yet supported",
            f"{source}.type",
        )
    elif challenge_type != "standard" and isinstance(raw_type, str):
        _error(
            diagnostics,
            "invalid_value",
            "Only standard challenges are supported",
            f"{source}.type",
        )
    logic = _enum(
        value.get("logic"), {"any", "all"}, f"{source}.logic", diagnostics
    )
    max_attempts = _integer(
        value.get("max_attempts"),
        f"{source}.max_attempts",
        diagnostics,
        minimum=0,
    )
    attribution = _string(
        value.get("attribution"), f"{source}.attribution", diagnostics
    )
    connection_info = _string(
        value.get("connection_info"), f"{source}.connection_info", diagnostics
    )

    raw_tags = value.get("tags")
    tags: list[str] = []
    if not isinstance(raw_tags, list):
        _error(diagnostics, "invalid_type", "Expected an array", f"{source}.tags")
    else:
        for tag_index, item in enumerate(raw_tags):
            tag = _string(
                item,
                f"{source}.tags[{tag_index}]",
                diagnostics,
                allow_empty=False,
                maximum=80,
            )
            if tag is not None:
                if tag in tags:
                    _error(
                        diagnostics,
                        "duplicate_tag",
                        f"Duplicate tag {tag!r}",
                        f"{source}.tags[{tag_index}]",
                    )
                tags.append(tag)

    raw_next = value.get("next")
    next_name: str | None
    if raw_next is None:
        next_name = None
    else:
        next_name = _string(
            raw_next,
            f"{source}.next",
            diagnostics,
            allow_empty=False,
            maximum=80,
        )

    solution = _solution(value.get("solution"), f"{source}.solution", diagnostics)

    flags: list[FlagSpec] = []
    raw_flags = value.get("flags")
    if not isinstance(raw_flags, list):
        _error(diagnostics, "invalid_type", "Expected an array", f"{source}.flags")
    else:
        for flag_index, item in enumerate(raw_flags):
            parsed = _flag(item, f"{source}.flags[{flag_index}]", diagnostics)
            if parsed is not None:
                if parsed in flags:
                    _error(
                        diagnostics,
                        "duplicate_flag",
                        "Duplicate flag",
                        f"{source}.flags[{flag_index}]",
                    )
                flags.append(parsed)

    hints: list[HintSpec] = []
    raw_hints = value.get("hints")
    if not isinstance(raw_hints, list):
        _error(diagnostics, "invalid_type", "Expected an array", f"{source}.hints")
    else:
        for hint_index, item in enumerate(raw_hints):
            parsed = _hint(item, f"{source}.hints[{hint_index}]", diagnostics)
            if parsed is not None:
                if any(existing.title == parsed.title for existing in hints):
                    _error(
                        diagnostics,
                        "duplicate_hint_title",
                        f"Duplicate hint title {parsed.title!r}",
                        f"{source}.hints[{hint_index}].title",
                    )
                hints.append(parsed)

    normalized_logic = logic
    if not flags and logic in {"any", "all"}:
        normalized_logic = "any"
        if logic == "all":
            _error(
                diagnostics,
                "flagless_logic_normalized",
                "Flagless challenge logic was normalized to any",
                f"{source}.logic",
                blocking=False,
            )

    required_values = (
        name,
        description,
        challenge_value,
        category,
        max_attempts,
        attribution,
        connection_info,
        solution,
    )
    if (
        any(item is None for item in required_values)
        or state not in {"hidden", "visible", "locked"}
        or challenge_type != "standard"
        or normalized_logic not in {"any", "all"}
    ):
        return None
    return ChallengeSpec(
        name=name,
        description=description,
        value=challenge_value,
        category=category,
        state=state,
        type="standard",
        logic=normalized_logic,
        max_attempts=max_attempts,
        attribution=attribution,
        connection_info=connection_info,
        tags=tuple(tags),
        next=next_name,
        solution=solution,
        flags=tuple(flags),
        hints=tuple(hints),
    )


def validate_manifest_data(
    data: object,
) -> tuple[Manifest | None, tuple[Diagnostic, ...]]:
    diagnostics: list[Diagnostic] = []
    if not isinstance(data, dict):
        _error(diagnostics, "invalid_type", "Expected a top-level object", "$")
        return None, tuple(diagnostics)
    _check_keys(data, TOP_KEYS, "", diagnostics)
    if data.get("format") != "push-challenges":
        _error(
            diagnostics,
            "unsupported_format",
            "Expected format 'push-challenges'",
            "format",
        )
    if type(data.get("version")) is not int or data.get("version") != 1:
        _error(diagnostics, "unsupported_version", "Expected version 1", "version")

    warnings: list[Diagnostic] = []
    raw_warnings = data.get("warnings")
    if not isinstance(raw_warnings, list):
        _error(diagnostics, "invalid_type", "Expected an array", "warnings")
    else:
        for index, item in enumerate(raw_warnings):
            parsed = _warning(item, index, diagnostics)
            if parsed is not None:
                warnings.append(parsed)

    challenges: list[ChallengeSpec] = []
    names: dict[str, int] = {}
    raw_challenges = data.get("challenges")
    if not isinstance(raw_challenges, list):
        _error(diagnostics, "invalid_type", "Expected an array", "challenges")
    else:
        for index, item in enumerate(raw_challenges):
            parsed = _challenge(item, index, diagnostics)
            if parsed is not None:
                if parsed.name in names:
                    _error(
                        diagnostics,
                        "duplicate_challenge_name",
                        (
                            f"Duplicate exact challenge name {parsed.name!r}; "
                            f"first used at challenges[{names[parsed.name]}]"
                        ),
                        f"challenges[{index}].name",
                    )
                else:
                    names[parsed.name] = index
                challenges.append(parsed)

    result_diagnostics = tuple(diagnostics)
    if any(item.blocking for item in result_diagnostics):
        return None, result_diagnostics
    return Manifest(tuple(warnings), tuple(challenges)), result_diagnostics


def load_manifest(path: Path) -> Manifest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        diagnostic = Diagnostic(
            "manifest_read_failed",
            str(error),
            str(path),
            True,
        )
        raise ManifestValidationError((diagnostic,)) from error
    manifest, diagnostics = validate_manifest_data(data)
    if manifest is None:
        raise ManifestValidationError(diagnostics)
    return manifest


def _solution_data(solution: SolutionSpec) -> dict[str, object]:
    return {
        "action": solution.action,
        "content": solution.content,
        "state": solution.state,
    }


def _challenge_data(challenge: ChallengeSpec) -> dict[str, object]:
    return {
        "name": challenge.name,
        "description": challenge.description,
        "value": challenge.value,
        "category": challenge.category,
        "state": challenge.state,
        "type": challenge.type,
        "logic": challenge.logic,
        "max_attempts": challenge.max_attempts,
        "attribution": challenge.attribution,
        "connection_info": challenge.connection_info,
        "tags": list(challenge.tags),
        "next": challenge.next,
        "solution": _solution_data(challenge.solution),
        "flags": [
            {"type": flag.type, "content": flag.content, "data": flag.data}
            for flag in challenge.flags
        ],
        "hints": [
            {
                "title": hint.title,
                "content": hint.content,
                "cost": hint.cost,
                "required_hints": list(hint.required_hints),
            }
            for hint in challenge.hints
        ],
    }


def dump_manifest(manifest: Manifest, path: Path) -> None:
    data = {
        "format": manifest.format,
        "version": manifest.version,
        "warnings": [warning.to_data() for warning in manifest.warnings],
        "challenges": [_challenge_data(challenge) for challenge in manifest.challenges],
    }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
