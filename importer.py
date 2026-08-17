"""CTFd-specific challenge import preflight and application."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

from CTFd.cache import clear_challenges, clear_standings
from CTFd.models import Challenges, Flags, Hints, Solutions, Tags, db

from .push_challenges_core.graph import find_cycle
from .push_challenges_core.model import ChallengeSpec, HintSpec, Manifest


class ImportPreflightError(ValueError):
    pass


class ImportApplyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChallengeAction:
    spec: ChallengeSpec
    existing_id: int | None
    mode: Literal["create", "overwrite"]
    changes: tuple[str, ...] = ()


@dataclass(frozen=True)
class HintAction:
    challenge_name: str
    spec: HintSpec
    existing_id: int | None
    mode: Literal["create", "update"]


@dataclass(frozen=True)
class ImportPlan:
    manifest: Manifest
    challenges: tuple[ChallengeAction, ...]
    hints: tuple[HintAction, ...]
    projected_next: Mapping[str, str | None]
    preserved_hint_counts: Mapping[str, int]


@dataclass(frozen=True)
class ApplyResult:
    committed: bool
    cache_warnings: tuple[str, ...]


def _group_by_name(rows) -> dict[str, list[object]]:
    grouped: defaultdict[str, list[object]] = defaultdict(list)
    for row in rows:
        grouped[row.name].append(row)
    return dict(grouped)


def _challenge_changes(challenge, spec: ChallengeSpec) -> tuple[str, ...]:
    if challenge is None:
        return (
            "name",
            "description",
            "value",
            "category",
            "state",
            "logic",
            "max_attempts",
            "attribution",
            "connection_info",
            "tags",
            "flags",
            "solution",
            "hints",
            "next",
        )
    scalar_fields = (
        "description",
        "value",
        "category",
        "state",
        "logic",
        "max_attempts",
        "attribution",
        "connection_info",
    )
    changes = [
        field
        for field in scalar_fields
        if getattr(challenge, field) != getattr(spec, field)
    ]
    changes.extend(("tags", "flags"))
    if spec.solution.action != "preserve":
        changes.append("solution")
    if spec.hints:
        changes.append("hints")
    changes.append("next")
    return tuple(changes)


def _format_conflicts(kind: str, name: str, rows: list[object]) -> str:
    ids = ", ".join(str(row.id) for row in rows)
    return f"Ambiguous {kind} exact name {name!r}; conflicting IDs: {ids}"


def build_plan(manifest: Manifest) -> ImportPlan:
    existing = Challenges.query.all()
    by_id = {challenge.id: challenge for challenge in existing}
    by_name = _group_by_name(existing)
    imported_names = {spec.name for spec in manifest.challenges}
    target_names = {
        spec.next for spec in manifest.challenges if spec.next is not None
    }
    for name in sorted(imported_names | target_names):
        matches = by_name.get(name, [])
        if len(matches) > 1:
            raise ImportPreflightError(
                _format_conflicts("challenge", name, matches)
            )

    actions: list[ChallengeAction] = []
    action_by_name: dict[str, ChallengeAction] = {}
    for spec in manifest.challenges:
        matches = by_name.get(spec.name, [])
        challenge = matches[0] if matches else None
        if challenge is not None and (
            challenge.type != "standard" or challenge.function != "static"
        ):
            raise ImportPreflightError(
                f"{spec.name!r} is not a fixed-value standard challenge"
            )
        action = ChallengeAction(
            spec=spec,
            existing_id=challenge.id if challenge is not None else None,
            mode="overwrite" if challenge is not None else "create",
            changes=_challenge_changes(challenge, spec),
        )
        actions.append(action)
        action_by_name[spec.name] = action

    node_for_database_id = {
        challenge.id: f"db:{challenge.id}" for challenge in existing
    }
    node_for_import_name = {
        action.spec.name: (
            node_for_database_id[action.existing_id]
            if action.existing_id is not None
            else f"new:{action.spec.name}"
        )
        for action in actions
    }
    labels = {
        node_for_database_id[challenge.id]: challenge.name
        for challenge in existing
    }
    labels.update(
        {
            node_for_import_name[action.spec.name]: action.spec.name
            for action in actions
        }
    )
    graph: dict[str, str | None] = {}
    for challenge in existing:
        graph[node_for_database_id[challenge.id]] = node_for_database_id.get(
            challenge.next_id
        )

    projected_next: dict[str, str | None] = {}
    for challenge in existing:
        target = by_id.get(challenge.next_id)
        projected_next.setdefault(
            challenge.name, target.name if target is not None else None
        )
    for action in actions:
        spec = action.spec
        source_node = node_for_import_name[spec.name]
        if spec.next is None:
            target_node = None
        elif spec.next in node_for_import_name:
            target_node = node_for_import_name[spec.next]
        else:
            matches = by_name.get(spec.next, [])
            if not matches:
                raise ImportPreflightError(
                    f"Unknown Next target {spec.next!r} for {spec.name!r}"
                )
            target_node = node_for_database_id[matches[0].id]
        graph[source_node] = target_node
        projected_next[spec.name] = spec.next

    cycle = find_cycle(graph)
    if cycle is not None:
        path = " -> ".join(labels[node] for node in cycle)
        raise ImportPreflightError(f"Circular Next chain: {path}")

    hint_actions: list[HintAction] = []
    preserved_hint_counts: dict[str, int] = {}
    for action in actions:
        existing_hints = (
            Hints.query.filter_by(challenge_id=action.existing_id).all()
            if action.existing_id is not None
            else []
        )
        hints_by_title = _group_by_name(
            [
                type(
                    "HintName",
                    (),
                    {"name": hint.title, "id": hint.id, "hint": hint},
                )()
                for hint in existing_hints
            ]
        )
        relevant_titles = {
            title
            for hint in action.spec.hints
            for title in (hint.title, *hint.required_hints)
        }
        for title in sorted(relevant_titles):
            matches = hints_by_title.get(title, [])
            if len(matches) > 1:
                raise ImportPreflightError(
                    _format_conflicts(
                        f"hint title in {action.spec.name!r}", title, matches
                    )
                )
        imported_titles = {hint.title for hint in action.spec.hints}
        projected_titles = set(hints_by_title) | imported_titles
        for hint in action.spec.hints:
            unknown = [
                title
                for title in hint.required_hints
                if title not in projected_titles
            ]
            if unknown:
                raise ImportPreflightError(
                    f"Unknown required hint title(s) for {action.spec.name!r} / "
                    f"{hint.title!r}: {', '.join(repr(item) for item in unknown)}"
                )
            matches = hints_by_title.get(hint.title, [])
            existing_id = matches[0].id if matches else None
            hint_actions.append(
                HintAction(
                    challenge_name=action.spec.name,
                    spec=hint,
                    existing_id=existing_id,
                    mode="update" if existing_id is not None else "create",
                )
            )
        preserved_hint_counts[action.spec.name] = sum(
            hint.title not in imported_titles for hint in existing_hints
        )

    return ImportPlan(
        manifest=manifest,
        challenges=tuple(actions),
        hints=tuple(hint_actions),
        projected_next=projected_next,
        preserved_hint_counts=preserved_hint_counts,
    )


def render_plan(plan: ImportPlan) -> str:
    lines: list[str] = []
    for warning in plan.manifest.warnings:
        lines.append(
            f"WARNING [{warning.code}] {warning.source}: {warning.message}"
        )
    for action in plan.challenges:
        lines.append(f"{action.mode.upper()}: {action.spec.name}")
        lines.append("  Fields: " + ", ".join(action.changes))
        lines.append(
            f"  Replace tags / flags: {len(action.spec.tags)} / "
            f"{len(action.spec.flags)}"
        )
        lines.append(
            f"  Solution: {action.spec.solution.action}; "
            f"Next: {action.spec.next or '(clear)'}"
        )
        challenge_hints = [
            hint for hint in plan.hints if hint.challenge_name == action.spec.name
        ]
        creates = sum(hint.mode == "create" for hint in challenge_hints)
        updates = sum(hint.mode == "update" for hint in challenge_hints)
        lines.append(
            f"  Hints create / update / preserve: {creates} / {updates} / "
            f"{plan.preserved_hint_counts[action.spec.name]}"
        )
        for hint in challenge_hints:
            required = ", ".join(hint.spec.required_hints) or "(none)"
            lines.append(
                f"    {hint.mode.upper()}: {hint.spec.title}; "
                f"requires: {required}"
            )
    return "\n".join(lines) + "\n"


def _call_stage(
    stage_hook: Callable[[str], None] | None, stage: str
) -> None:
    if stage_hook is not None:
        stage_hook(stage)


def _recheck_plan(plan: ImportPlan) -> None:
    existing = Challenges.query.all()
    by_name = _group_by_name(existing)
    for action in plan.challenges:
        matches = by_name.get(action.spec.name, [])
        if action.mode == "create":
            if matches:
                raise ImportPreflightError(
                    f"{action.spec.name!r} appeared after preflight"
                )
            continue
        if len(matches) != 1 or matches[0].id != action.existing_id:
            ids = ", ".join(str(row.id) for row in matches) or "(none)"
            raise ImportPreflightError(
                f"{action.spec.name!r} changed after preflight; current IDs: {ids}"
            )
        if matches[0].type != "standard" or matches[0].function != "static":
            raise ImportPreflightError(
                f"{action.spec.name!r} is no longer a fixed-value "
                "standard challenge"
            )
    for action in plan.hints:
        if action.existing_id is None:
            continue
        hint = Hints.query.get(action.existing_id)
        challenge_action = next(
            item
            for item in plan.challenges
            if item.spec.name == action.challenge_name
        )
        if (
            hint is None
            or hint.title != action.spec.title
            or hint.challenge_id != challenge_action.existing_id
        ):
            raise ImportPreflightError(
                f"Hint {action.existing_id} changed after preflight"
            )


def apply_plan(
    plan: ImportPlan,
    stage_hook: Callable[[str], None] | None = None,
) -> ApplyResult:
    """Apply an immutable plan in one transaction and one commit."""
    try:
        _recheck_plan(plan)
        challenge_rows: dict[str, Challenges] = {}
        for action in plan.challenges:
            if action.existing_id is None:
                challenge = Challenges(
                    name=action.spec.name,
                    type="standard",
                    function="static",
                )
                db.session.add(challenge)
            else:
                challenge = Challenges.query.get(action.existing_id)
                if challenge is None:
                    raise ImportPreflightError(
                        f"Challenge {action.existing_id} disappeared after preflight"
                    )
            spec = action.spec
            challenge.name = spec.name
            challenge.description = spec.description
            challenge.value = spec.value
            challenge.category = spec.category
            challenge.state = spec.state
            challenge.type = "standard"
            challenge.function = "static"
            challenge.logic = spec.logic if spec.flags else "any"
            challenge.max_attempts = spec.max_attempts
            challenge.attribution = spec.attribution
            challenge.connection_info = spec.connection_info
            challenge_rows[spec.name] = challenge
        db.session.flush()
        _call_stage(stage_hook, "after_challenges")

        imported_ids = tuple(row.id for row in challenge_rows.values())
        if imported_ids:
            Flags.query.filter(Flags.challenge_id.in_(imported_ids)).delete(
                synchronize_session=False
            )
            Tags.query.filter(Tags.challenge_id.in_(imported_ids)).delete(
                synchronize_session=False
            )
        flag_rows: list[dict[str, object]] = []
        for action in plan.challenges:
            challenge = challenge_rows[action.spec.name]
            db.session.add_all(
                [
                    Tags(challenge_id=challenge.id, value=value)
                    for value in action.spec.tags
                ]
            )
            flag_rows.extend(
                {
                    "challenge_id": challenge.id,
                    "type": flag.type,
                    "content": flag.content,
                    "data": flag.data,
                }
                for flag in action.spec.flags
            )
        if flag_rows:
            db.session.execute(Flags.__table__.insert(), flag_rows)
        _call_stage(stage_hook, "after_replacements")

        for action in plan.challenges:
            solution_spec = action.spec.solution
            if solution_spec.action == "preserve":
                continue
            challenge = challenge_rows[action.spec.name]
            solution = Solutions.query.filter_by(
                challenge_id=challenge.id
            ).one_or_none()
            if solution_spec.action == "upsert":
                if solution is None:
                    solution = Solutions(challenge_id=challenge.id)
                    db.session.add(solution)
                solution.content = solution_spec.content
                solution.state = solution_spec.state
            elif solution is not None:
                solution.content = ""
                solution.state = "hidden"
        _call_stage(stage_hook, "after_solutions")

        hint_rows: dict[tuple[str, str], Hints] = {}
        for action in plan.hints:
            challenge = challenge_rows[action.challenge_name]
            if action.existing_id is None:
                hint = Hints(
                    challenge_id=challenge.id,
                    type="standard",
                    title=action.spec.title,
                )
                db.session.add(hint)
            else:
                hint = Hints.query.get(action.existing_id)
                if hint is None:
                    raise ImportPreflightError(
                        f"Hint {action.existing_id} disappeared after preflight"
                    )
            hint.title = action.spec.title
            hint.content = action.spec.content
            hint.cost = action.spec.cost
            hint_rows[(action.challenge_name, action.spec.title)] = hint
        db.session.flush()
        _call_stage(stage_hook, "after_hints")

        for action in plan.hints:
            hint = hint_rows[(action.challenge_name, action.spec.title)]
            prerequisite_ids: list[int] = []
            for title in action.spec.required_hints:
                prerequisite = hint_rows.get((action.challenge_name, title))
                if prerequisite is None:
                    challenge = challenge_rows[action.challenge_name]
                    prerequisite = Hints.query.filter_by(
                        challenge_id=challenge.id, title=title
                    ).one_or_none()
                if prerequisite is None:
                    raise ImportPreflightError(
                        f"Required hint {title!r} disappeared after preflight"
                    )
                prerequisite_ids.append(prerequisite.id)
            hint.requirements = {"prerequisites": prerequisite_ids}
        _call_stage(stage_hook, "after_requirements")

        existing_targets = _group_by_name(Challenges.query.all())
        for action in plan.challenges:
            challenge = challenge_rows[action.spec.name]
            if action.spec.next is None:
                challenge.next_id = None
                continue
            target = challenge_rows.get(action.spec.next)
            if target is None:
                matches = existing_targets.get(action.spec.next, [])
                if len(matches) != 1:
                    raise ImportPreflightError(
                        f"Next target {action.spec.next!r} changed after preflight"
                    )
                target = matches[0]
            challenge.next_id = target.id
        _call_stage(stage_hook, "after_next")
        db.session.commit()
    except Exception as error:
        db.session.rollback()
        raise ImportApplyError(
            f"Import failed; database transaction was rolled back: {error}"
        ) from error

    cache_warnings: list[str] = []
    for name, clear in (
        ("clear_challenges", clear_challenges),
        ("clear_standings", clear_standings),
    ):
        try:
            clear()
        except Exception as error:
            cache_warnings.append(f"{name}: {error}")
    return ApplyResult(True, tuple(cache_warnings))
