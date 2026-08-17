from conftest import challenge_data, manifest_data
from CTFd.models import Challenges


def test_plugin_registers_push_challenges_command(app, runner):
    result = runner.invoke(args=["push-challenges", "--help"])

    assert result.exit_code == 0
    assert "import" in result.output


def test_dry_run_reports_create_without_writing(app, runner, manifest_path):
    result = runner.invoke(
        args=["push-challenges", "import", str(manifest_path)]
    )

    assert result.exit_code == 0
    assert "CREATE: Example" in result.output
    assert Challenges.query.count() == 0


def test_dry_run_prints_persisted_authoring_warning(
    app, runner, write_manifest
):
    warning = {
        "code": "orphan_hint_ignored",
        "message": "Hint for Deleted was ignored",
        "source": "Hints!A8",
        "blocking": False,
    }
    path = write_manifest(manifest_data(challenge_data(), warnings=[warning]))

    result = runner.invoke(args=["push-challenges", "import", str(path)])

    assert result.exit_code == 0
    assert "WARNING [orphan_hint_ignored]" in result.output
    assert "Hints!A8" in result.output


def test_invalid_manifest_exits_nonzero_without_traceback(
    app, runner, write_manifest
):
    path = write_manifest({"format": "wrong", "version": 1})

    result = runner.invoke(args=["push-challenges", "import", str(path)])

    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "missing" in result.output.lower() or "expected" in result.output.lower()


def test_apply_flag_commits_instead_of_reporting_dry_run(
    app, runner, manifest_path
):
    result = runner.invoke(
        args=[
            "push-challenges",
            "import",
            str(manifest_path),
            "--apply",
        ]
    )

    assert result.exit_code == 0
    assert "APPLIED: database transaction committed." in result.output
    assert "DRY RUN" not in result.output
    assert Challenges.query.filter_by(name="Example").one() is not None
