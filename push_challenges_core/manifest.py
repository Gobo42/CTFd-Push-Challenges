"""Strict loading, validation, and writing of canonical manifests."""

from __future__ import annotations

import dataclasses
import json
from decimal import ROUND_DOWN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .errors import Diagnostic, ManifestValidationError
from .model import (
    BonusSpec,
    BonusTierSpec,
    ChallengeSpec,
    DynamicScoringSpec,
    FlagSpec,
    HintSpec,
    Manifest,
    SolutionSpec,
)

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


def _flag(value: object, source: str, diagnostics: list[Diagnostic]) -> FlagSpec | None:
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


def _hint(value: object, source: str, diagnostics: list[Diagnostic]) -> HintSpec | None:
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


def _scoring(value, challenge_type, initial, source, diagnostics):
    if challenge_type == "standard":
        if value is not None:
            _error(
                diagnostics, "invalid_scoring", "Standard scoring must be null", source
            )
        return None
    if not isinstance(value, dict):
        _error(
            diagnostics,
            "invalid_scoring",
            "Dynamic scoring settings are required",
            source,
        )
        return None
    _check_keys(value, {"function", "minimum", "decay"}, source, diagnostics)
    function = _enum(
        value.get("function"),
        {"linear", "logarithmic"},
        f"{source}.function",
        diagnostics,
    )
    minimum = _integer(
        value.get("minimum"), f"{source}.minimum", diagnostics, minimum=0
    )
    decay = _integer(value.get("decay"), f"{source}.decay", diagnostics, minimum=1)
    if type(initial) is int and (initial < 0 or initial > 2_147_483_647):
        _error(
            diagnostics,
            "invalid_scoring",
            "Dynamic Value must be between 0 and 2147483647",
            source,
        )
    if minimum is not None and type(initial) is int and minimum > initial:
        _error(
            diagnostics,
            "invalid_scoring",
            "Minimum Value must not exceed Value",
            f"{source}.minimum",
        )
    if decay is not None and decay > 2_147_483_647:
        _error(
            diagnostics,
            "invalid_scoring",
            "Decay exceeds CTFd integer range",
            f"{source}.decay",
        )
    if function not in {"linear", "logarithmic"} or minimum is None or decay is None:
        return None
    return DynamicScoringSpec(function, minimum, decay)


def _bonus(value, source, diagnostics):
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_bonus", "Expected a bonus object", source)
        return BonusSpec()
    _check_keys(value, {"mode", "tiers"}, source, diagnostics)
    mode = _enum(
        value.get("mode"),
        {"preserve", "disabled", "absolute", "percentage"},
        f"{source}.mode",
        diagnostics,
    )
    rows = value.get("tiers")
    if not isinstance(rows, list):
        _error(diagnostics, "invalid_bonus", "Expected a tier array", source)
        return BonusSpec()
    if mode in {"preserve", "disabled"}:
        if rows:
            _error(
                diagnostics,
                "invalid_bonus",
                "Preserve/disabled cannot include tiers",
                source,
            )
        return BonusSpec(mode)
    if not rows:
        _error(diagnostics, "invalid_bonus", "At least one tier is required", source)
    tiers = []
    expected_start = 1
    for index, row in enumerate(rows):
        tier_source = f"{source}.tiers[{index}]"
        if not isinstance(row, dict):
            _error(diagnostics, "invalid_bonus", "Expected a tier object", tier_source)
            continue
        _check_keys(row, {"start", "end", "amount"}, tier_source, diagnostics)
        start = _integer(
            row.get("start"), f"{tier_source}.start", diagnostics, minimum=1
        )
        end = _integer(row.get("end"), f"{tier_source}.end", diagnostics, minimum=1)
        if start != expected_start or end is None or start is None or end < start:
            _error(
                diagnostics,
                "invalid_bonus",
                "Tier ranges must start at 1 and be contiguous "
                "without gaps or overlaps",
                tier_source,
            )
        if end is not None:
            expected_start = end + 1
            if end > 2_147_483_647:
                _error(
                    diagnostics,
                    "invalid_bonus",
                    "Placement exceeds CTFd integer range",
                    tier_source,
                )
        raw_amount = _string(row.get("amount"), f"{tier_source}.amount", diagnostics)
        try:
            amount = Decimal(raw_amount) if raw_amount is not None else Decimal("NaN")
            if (
                not amount.is_finite()
                or amount < 0
                or amount > Decimal("9999999999.99")
            ):
                raise ValueError(
                    "Amount must be finite, nonnegative, and fit 10 whole digits"
                )
            if mode == "absolute" and (
                amount != amount.to_integral_value() or amount > 2_147_483_647
            ):
                raise ValueError(
                    "Absolute amount must be whole points in CTFd integer range"
                )
            amount = amount.quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        except (InvalidOperation, ValueError):
            _error(
                diagnostics,
                "invalid_bonus",
                "Invalid bonus amount",
                f"{tier_source}.amount",
            )
            continue
        if start is not None and end is not None:
            tiers.append(BonusTierSpec(start, end, str(amount)))
    return BonusSpec(mode, tuple(tiers))


def _challenge(
    value: object, index: int, diagnostics: list[Diagnostic], version: int = 1
) -> ChallengeSpec | None:
    source = f"challenges[{index}]"
    if not isinstance(value, dict):
        _error(diagnostics, "invalid_type", "Expected an object", source)
        return None
    keys = CHALLENGE_KEYS | {"scoring", "bonus"} if version == 2 else CHALLENGE_KEYS
    if version == 2 and "position" in value:
        keys |= {"position"}
    _check_keys(value, keys, source, diagnostics)
    position = None
    if version == 2 and value.get("position") is not None:
        position = _integer(
            value["position"], f"{source}.position", diagnostics, minimum=0
        )
        if position is not None and position > 2_147_483_647:
            _error(
                diagnostics,
                "value_out_of_range",
                "Position exceeds CTFd integer range",
                f"{source}.position",
            )
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
    if challenge_type == "dynamic" and version == 1:
        _error(
            diagnostics,
            "unsupported_challenge_type",
            "Dynamic requires manifest version 2",
            f"{source}.type",
        )
    elif challenge_type not in {"standard", "dynamic"} and isinstance(raw_type, str):
        _error(
            diagnostics,
            "invalid_value",
            "Only standard and dynamic challenges are supported",
            f"{source}.type",
        )
    scoring = (
        _scoring(
            value.get("scoring"),
            challenge_type,
            challenge_value,
            f"{source}.scoring",
            diagnostics,
        )
        if version == 2
        else None
    )
    bonus = (
        _bonus(value.get("bonus"), f"{source}.bonus", diagnostics)
        if version == 2
        else BonusSpec()
    )
    logic = _enum(value.get("logic"), {"any", "all"}, f"{source}.logic", diagnostics)
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
        or challenge_type not in {"standard", "dynamic"}
        or normalized_logic not in {"any", "all"}
    ):
        return None
    return ChallengeSpec(
        name=name,
        description=description,
        value=challenge_value,
        category=category,
        state=state,
        type=challenge_type,
        logic=normalized_logic,
        max_attempts=max_attempts,
        attribution=attribution,
        connection_info=connection_info,
        tags=tuple(tags),
        next=next_name,
        solution=solution,
        flags=tuple(flags),
        hints=tuple(hints),
        scoring=scoring,
        bonus=bonus,
        position=position,
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
    version = data.get("version")
    if type(version) is not int or version not in (1, 2):
        _error(diagnostics, "unsupported_version", "Expected version 1 or 2", "version")

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
            parsed = _challenge(item, index, diagnostics, version)
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
    return Manifest(
        tuple(warnings), tuple(challenges), version=version
    ), result_diagnostics


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


def dump_manifest(manifest: Manifest, path: Path) -> None:
    challenges = [dataclasses.asdict(challenge) for challenge in manifest.challenges]
    if manifest.version == 1:
        for challenge in challenges:
            challenge.pop("scoring")
            challenge.pop("bonus")
            challenge.pop("position")
    data = {
        "format": manifest.format,
        "version": manifest.version,
        "warnings": [warning.to_data() for warning in manifest.warnings],
        "challenges": challenges,
    }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
