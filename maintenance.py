"""Interactive challenge maintenance using CTFd's native deletion handlers."""

from __future__ import annotations

import re

import click
from CTFd.cache import clear_challenges, clear_standings
from CTFd.models import Challenges, db
from CTFd.plugins.challenges import get_chal_class
from flask.cli import with_appcontext


def _challenge_rows():
    return (
        Challenges.query.with_entities(
            Challenges.id,
            Challenges.name,
            Challenges.category,
            Challenges.type,
            Challenges.value,
            Challenges.state,
        )
        .order_by(Challenges.id)
        .all()
    )


def _show_challenges(rows) -> None:
    click.echo("ID\tName\tCategory\tType\tPoints\tState")
    for row in rows:
        click.echo(
            f"{row.id}\t{row.name!r}\t{row.category!r}\t"
            f"{row.type}\t{row.value}\t{row.state}"
        )


def _select_ids(selection: str, existing_ids: set[int]) -> list[int]:
    selected = set()
    for part in selection.split(","):
        match = re.fullmatch(r"([0-9]+)(?:\s*-\s*([0-9]+))?", part.strip())
        if match is None:
            raise click.ClickException(f"Invalid selection {part!r}; use IDs or N-M.")
        try:
            start = int(match[1])
            end = int(match[2]) if match[2] is not None else start
        except ValueError as error:
            raise click.ClickException("Invalid challenge ID.") from error
        if start < 1 or end < start:
            raise click.ClickException(f"Invalid ID or reversed range: {part!r}.")
        matches = {item for item in existing_ids if start <= item <= end}
        if len(matches) != end - start + 1:
            raise click.ClickException(
                f"Selection {part!r} includes nonexistent challenge IDs. "
                "Run 'push-challenges list' again; nothing was deleted."
            )
        selected.update(matches)
    return sorted(selected)


@click.command("list")
@with_appcontext
def list_challenges() -> None:
    """List actual challenge IDs, names, categories, types, points, and states."""
    rows = _challenge_rows()
    if not rows:
        click.echo("No challenges found.")
        return
    _show_challenges(rows)


@click.command("delete")
@click.argument("selection", required=False)
@with_appcontext
def delete_challenges(selection: str | None) -> None:
    """Delete SELECTION (47,49,55-58), or list and prompt when omitted.

    Preview the full selection and require literal 'yes' before deleting.
    Uses native CTFd cleanup, including associated data and attached files.
    Each challenge commits separately; the batch is not atomic.
    """
    rows = _challenge_rows()
    if not rows:
        click.echo("No challenges found.")
        return
    if selection is None:
        _show_challenges(rows)
        selection = click.prompt("Challenge IDs to delete (e.g. 47,49,55-58)")
    ids = _select_ids(selection, {row.id for row in rows})
    by_id = {row.id: row for row in rows}
    targets = [by_id[item] for item in ids]
    for row in targets:
        try:
            get_chal_class(row.type)
        except KeyError as error:
            raise click.ClickException(
                f"Challenge {row.id} has unavailable type {row.type!r}; "
                "nothing was deleted."
            ) from error

    click.echo(f"Selected {len(targets)} challenges for permanent deletion:")
    _show_challenges(targets)
    click.echo(
        "WARNING: associated solves, submissions, flags, hints, solutions, and "
        "attached files are removed using CTFd's native handler. "
        "Take a CTFd database and upload backup first. "
        "Deletions commit individually; even a failure may leave partial cleanup."
    )
    if click.prompt("Type yes to delete", default="no") != "yes":
        click.echo("Cancelled; nothing was deleted.")
        return

    db.session.rollback()
    deleted = 0
    failures = []
    cache_errors = []
    try:
        for row in targets:
            try:
                challenge = Challenges.query.filter_by(id=row.id).first()
                if challenge is None or (challenge.name, challenge.type) != (
                    row.name,
                    row.type,
                ):
                    raise RuntimeError("challenge changed since preview; list again")
                get_chal_class(challenge.type).delete(challenge)
                if Challenges.query.filter_by(id=row.id).count():
                    raise RuntimeError("native deletion handler left the challenge")
                deleted += 1
                click.echo(f"DELETED: {row.id} {row.name!r}")
            except Exception as error:
                db.session.rollback()
                failures.append(row.id)
                click.echo(f"FAILED: {row.id} {row.name!r}: {error}", err=True)
    finally:
        db.session.rollback()
        for clear in (clear_standings, clear_challenges):
            try:
                clear()
            except Exception as error:
                cache_errors.append(str(error))
                click.echo(f"WARNING: cache refresh failed: {error}", err=True)

    click.echo(f"Deletion summary: deleted: {deleted}; failed: {len(failures)}.")
    if failures:
        click.echo(
            "MANUAL ACTION REQUIRED: failed IDs: " + ",".join(map(str, failures))
        )
    if failures or cache_errors:
        raise click.ClickException(
            "Deletion or cache refresh was incomplete. Completed deletions remain "
            "committed. Review failures and list remaining challenges before retrying."
        )
