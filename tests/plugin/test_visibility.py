import importlib
import io

import click
import pytest
from CTFd.models import (
    Challenges,
    Files,
    Flags,
    Hints,
    Solutions,
    Submissions,
    Tags,
    db,
)
from CTFd.plugins.dynamic_challenges import DynamicChallenge
from CTFd.utils.uploads import upload_file
from test_preflight import persisted_challenge
from tests.helpers import (
    gen_fail,
    gen_flag,
    gen_hint,
    gen_solution,
    gen_solve,
    gen_tag,
    gen_user,
)
from werkzeug.datastructures import FileStorage


@pytest.mark.parametrize(
    "command,source,target",
    [("hide", "visible", "hidden"), ("unhide", "hidden", "visible")],
)
def test_visibility_selection_changes_only_challenge_state(
    app, runner, tmp_path, command, source, target
):
    from CTFd.utils.challenges import get_all_challenges

    rows = [
        persisted_challenge(name)
        for name in ("First", "Second", "Same", "Locked", "Keep")
    ]
    ids = [row.id for row in rows]
    for row, state in zip(
        rows, (source, source, target, "locked", source), strict=True
    ):
        row.state = state
    db.session.commit()
    user = gen_user(db)
    gen_solve(db, user_id=user.id, challenge_id=ids[0])
    gen_fail(db, user_id=user.id, challenge_id=ids[0])
    gen_flag(db, challenge_id=ids[0])
    gen_tag(db, challenge_id=ids[0])
    gen_hint(db, challenge_id=ids[0])
    solution = gen_solution(db, challenge_id=ids[0])
    solution.state = "visible"
    db.session.commit()
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    for kind, key, value in (
        ("challenge", "challenge_id", ids[0]),
        ("solution", "solution_id", solution.id),
    ):
        upload_file(
            file=FileStorage(stream=io.BytesIO(b"preserve"), filename="test.txt"),
            type=kind,
            **{key: value},
        )
    paths = [tmp_path / row.location for row in Files.query.all()]
    models = (Flags, Hints, Solutions, Submissions, Tags, Files)
    before = {
        model: db.session.execute(model.__table__.select()).fetchall()
        for model in models
    }
    challenge_before = db.session.execute(Challenges.__table__.select()).fetchall()
    visible_before = {row.id for row in get_all_challenges()}

    result = runner.invoke(
        args=["push-challenges", command],
        input=f"{ids[0]}, {ids[1]}-{ids[3]}, {ids[0]}\nyes\n",
    )

    assert result.exit_code == 0, result.output
    assert "changed: 2; unchanged: 1; skipped: 1" in result.output
    assert f"SKIPPED: {ids[3]}" in result.output and "locked" in result.output
    assert "Challenge IDs" in result.output and "Keep" in result.output
    after = db.session.execute(Challenges.__table__.select()).fetchall()
    assert [row.state for row in after] == [target, target, target, "locked", source]
    for old, new in zip(challenge_before, after, strict=True):
        assert {k: v for k, v in old._mapping.items() if k != "state"} == {
            k: v for k, v in new._mapping.items() if k != "state"
        }
    for model in models:
        assert db.session.execute(model.__table__.select()).fetchall() == before[model]
    assert all(path.read_bytes() == b"preserve" for path in paths)
    visible_after = {row.id for row in get_all_challenges()}
    assert visible_after == (
        visible_before - set(ids[:2])
        if command == "hide"
        else visible_before | set(ids[:2])
    )


@pytest.mark.parametrize("command,source", [("hide", "visible"), ("unhide", "hidden")])
@pytest.mark.parametrize("answer", ["no\n", "y\n", "YES\n", ""])
def test_visibility_requires_literal_yes(app, runner, command, source, answer):
    row = persisted_challenge("Keep")
    row.state = source
    db.session.commit()
    result = runner.invoke(args=["push-challenges", command, str(row.id)], input=answer)
    assert "Type yes" in result.output
    assert Challenges.query.one().state == source
    assert "CHANGED:" not in result.output


@pytest.mark.parametrize("command", ["hide", "unhide"])
@pytest.mark.parametrize(
    "selection", ["", "0", "1-0", "1,,2", "1,9999", "1-2147483647"]
)
def test_visibility_rejects_invalid_selection_before_writing(
    app, runner, command, selection
):
    persisted_challenge("Keep")
    result = runner.invoke(args=["push-challenges", command, selection], input="yes\n")
    assert result.exit_code != 0
    assert "Invalid" in result.output or "nonexistent" in result.output
    assert Challenges.query.one().state == "visible"
    assert "CHANGED:" not in result.output


@pytest.mark.parametrize("command,target", [("hide", "hidden"), ("unhide", "visible")])
@pytest.mark.parametrize("state", ["locked", "nonstandard", "target"])
def test_visibility_noop_or_skipped_selection_needs_no_confirmation(
    app, runner, command, target, state
):
    row = persisted_challenge("Keep")
    row.state = target if state == "target" else state
    expected = row.state
    db.session.commit()
    result = runner.invoke(args=["push-challenges", command, str(row.id)], input="")
    assert result.exit_code == 0, result.output
    assert Challenges.query.one().state == expected
    assert "Type yes" not in result.output
    assert "No visibility changes needed" in result.output
    if state != "target":
        assert "SKIPPED:" in result.output and state in result.output


@pytest.mark.parametrize("command", ["hide", "unhide"])
def test_visibility_empty_installation_has_no_prompt(app, runner, command):
    result = runner.invoke(args=["push-challenges", command])
    assert result.exit_code == 0, result.output
    assert "No challenges found" in result.output


@pytest.mark.parametrize("change", ["name", "type", "state", "delete"])
def test_visibility_changed_target_rolls_back_earlier_updates(
    app, runner, monkeypatch, change
):
    ids = [persisted_challenge(name).id for name in ("First", "Changed")]
    prompt = click.prompt

    def change_during_confirmation(*args, **kwargs):
        answer = prompt(*args, **kwargs)
        query = db.session.query(Challenges.__table__).filter(Challenges.id == ids[1])
        if change == "delete":
            query.delete(synchronize_session=False)
        else:
            query.update(
                {
                    change: {"name": "Renamed", "type": "other", "state": "locked"}[
                        change
                    ]
                },
                synchronize_session=False,
            )
        db.session.commit()
        return answer

    monkeypatch.setattr(click, "prompt", change_during_confirmation)
    result = runner.invoke(
        args=["push-challenges", "hide", f"{ids[0]}-{ids[1]}"], input="yes\n"
    )
    assert result.exit_code != 0
    assert "changed since preview" in result.output
    assert "rolled back" in result.output
    assert Challenges.query.filter_by(id=ids[0]).one().state == "visible"
    assert "CHANGED:" not in result.output


def test_visibility_commit_failure_rolls_back_every_update(app, runner, monkeypatch):
    ids = [persisted_challenge(name).id for name in ("First", "Second")]

    def commit_failure():
        raise RuntimeError("injected commit failure")

    monkeypatch.setattr(db.session, "commit", commit_failure)
    result = runner.invoke(
        args=["push-challenges", "hide", f"{ids[0]}-{ids[1]}"], input="yes\n"
    )
    assert result.exit_code != 0
    assert "injected commit failure" in result.output and "rolled back" in result.output
    assert [row.state for row in Challenges.query.all()] == ["visible", "visible"]
    assert "CHANGED:" not in result.output


def test_visibility_cache_failure_reports_committed_changes_and_clears_other_cache(
    app, runner, monkeypatch
):
    from CTFd.utils.challenges import get_all_challenges

    maintenance = importlib.import_module("CTFd.plugins.push-challenges.maintenance")
    row = persisted_challenge("Hide")
    assert len(get_all_challenges()) == 1

    def cache_failure():
        raise RuntimeError("injected cache failure")

    monkeypatch.setattr(maintenance, "clear_standings", cache_failure)
    result = runner.invoke(args=["push-challenges", "hide", str(row.id)], input="yes\n")
    assert result.exit_code != 0
    assert Challenges.query.one().state == "hidden"
    assert get_all_challenges() == []
    assert "injected cache failure" in result.output
    assert "remain committed" in result.output
    assert "rolled back" not in result.output
    assert "changed: 1" in result.output


def test_visibility_changes_dynamic_state_without_touching_scoring(app, runner):
    row = DynamicChallenge(
        name="Dynamic",
        type="dynamic",
        state="visible",
        value=80,
        initial=100,
        minimum=10,
        decay=5,
        function="linear",
    )
    db.session.add(row)
    db.session.commit()
    before = db.session.execute(DynamicChallenge.__table__.select()).fetchall()
    result = runner.invoke(args=["push-challenges", "hide", str(row.id)], input="yes\n")
    assert result.exit_code == 0, result.output
    assert Challenges.query.one().state == "hidden"
    assert db.session.execute(DynamicChallenge.__table__.select()).fetchall() == before


def test_visibility_help_explains_challenge_only_scope_and_locked_skips(app, runner):
    for command in ("hide", "unhide"):
        result = runner.invoke(args=["push-challenges", command, "--help"])
        assert result.exit_code == 0, result.output
        assert "locked" in result.output.lower()
        assert "solution" in result.output.lower()
