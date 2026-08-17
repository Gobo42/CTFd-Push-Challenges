"""Flask CLI registration for challenge imports."""

from __future__ import annotations

import traceback
from pathlib import Path

import click
from flask.cli import AppGroup

from .importer import ImportPreflightError, build_plan, render_plan
from .push_challenges_core.errors import ManifestValidationError
from .push_challenges_core.manifest import load_manifest

push_challenges_cli = AppGroup(
    "push-challenges",
    help="Validate and atomically import challenge manifests.",
)


def _manifest_error(error: ManifestValidationError) -> click.ClickException:
    lines = [
        f"{item.source}: {item.message}"
        for item in error.diagnostics
        if item.blocking
    ]
    return click.ClickException("\n".join(lines))


@push_challenges_cli.command("import")
@click.argument(
    "manifest_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option("--apply", "should_apply", is_flag=True, help="Commit the plan.")
@click.option("--debug", is_flag=True, help="Show unexpected tracebacks.")
def import_manifest(
    manifest_file: Path, should_apply: bool, debug: bool
) -> None:
    """Validate MANIFEST_FILE and print or apply its complete plan."""
    try:
        manifest = load_manifest(manifest_file)
        plan = build_plan(manifest)
        click.echo(render_plan(plan), nl=False)
        if not should_apply:
            click.echo("DRY RUN: no database changes were made.")
            return
        from .importer import apply_plan

        result = apply_plan(plan)
        click.echo("APPLIED: database transaction committed.")
        for warning in result.cache_warnings:
            click.echo(f"WARNING [cache_invalidation_failed] {warning}")
    except ManifestValidationError as error:
        raise _manifest_error(error) from error
    except ImportPreflightError as error:
        raise click.ClickException(str(error)) from error
    except click.ClickException:
        raise
    except Exception as error:
        if debug:
            click.echo(traceback.format_exc(), err=True)
        raise click.ClickException(str(error)) from error


def register_cli(app) -> None:
    if "push-challenges" not in app.cli.commands:
        app.cli.add_command(push_challenges_cli)
