import importlib
import io

import pytest
from CTFd.models import (
    Challenges,
    Files,
    Flags,
    Hints,
    HintUnlocks,
    Solutions,
    SolutionUnlocks,
    Submissions,
    Tags,
    db,
)
from CTFd.plugins.challenges import BaseChallenge
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


def test_list_shows_real_ids_and_leaves_challenges_unchanged(app, runner):
    challenge = persisted_challenge("Listed")
    challenge_id = challenge.id
    result = runner.invoke(args=["push-challenges", "list"])
    assert result.exit_code == 0, result.output
    assert str(challenge_id) in result.output
    for value in ("Listed", "Old", "standard", "50", "visible"):
        assert value in result.output
    assert Challenges.query.count() == 1


def test_interactive_selection_deletes_ranges_once_and_keeps_other_ids(app, runner):
    rows = [persisted_challenge(f"Challenge {index}") for index in range(5)]
    ids = [row.id for row in rows]
    result = runner.invoke(
        args=["push-challenges", "delete"],
        input=f"{ids[0]}, {ids[2]}-{ids[3]}, {ids[2]}\nyes\n",
    )
    assert result.exit_code == 0, result.output
    assert [row.id for row in Challenges.query.order_by(Challenges.id)] == [
        ids[1],
        ids[4],
    ]
    assert "deleted: 3" in result.output
    assert result.output.count("DELETED:") == 3
    assert "Challenge 4" in result.output


@pytest.mark.parametrize(
    "selection", ["", "0", "-1", "1-0", "1,,2", "1,", "1-two", "1.5", "all"]
)
def test_invalid_selection_cannot_delete_any_challenge(app, runner, selection):
    persisted_challenge("Keep")
    result = runner.invoke(args=["push-challenges", "delete", selection], input="yes\n")
    assert result.exit_code != 0
    assert Challenges.query.count() == 1
    assert "DELETED:" not in result.output


@pytest.mark.parametrize("selection", ["1,9999", "1-9999", "1-2147483647"])
def test_missing_ids_reject_entire_selection_without_expanding_huge_ranges(
    app, runner, selection
):
    persisted_challenge("Keep")
    result = runner.invoke(args=["push-challenges", "delete", selection], input="yes\n")
    assert result.exit_code != 0
    assert "exist" in result.output.lower()
    assert Challenges.query.count() == 1


@pytest.mark.parametrize("confirmation", ["no\n", "y\n", "YES\n", ""])
def test_only_literal_yes_can_confirm_deletion(app, runner, confirmation):
    challenge = persisted_challenge("Keep")
    result = runner.invoke(
        args=["push-challenges", "delete", str(challenge.id)], input=confirmation
    )
    assert Challenges.query.count() == 1
    assert "DELETED:" not in result.output


def test_empty_installation_needs_no_selection_or_confirmation(app, runner):
    result = runner.invoke(args=["push-challenges", "delete"])
    assert result.exit_code == 0, result.output
    assert "No challenges" in result.output


def test_native_cleanup_removes_selected_data_files_and_refreshes_cache(
    app, runner, tmp_path
):
    from CTFd.utils.challenges import get_all_challenges

    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    selected = persisted_challenge("Remove")
    kept = persisted_challenge("Keep")
    kept_id = kept.id
    user = gen_user(db)
    gen_solve(db, user_id=user.id, challenge_id=selected.id)
    gen_fail(db, user_id=user.id, challenge_id=selected.id)
    gen_flag(db, challenge_id=selected.id)
    gen_tag(db, challenge_id=selected.id)
    gen_hint(db, challenge_id=selected.id)
    solution = gen_solution(db, challenge_id=selected.id)
    for target in ({"challenge_id": selected.id}, {"solution_id": solution.id}):
        file_type = "challenge" if "challenge_id" in target else "solution"
        upload_file(
            file=FileStorage(stream=io.BytesIO(b"attached"), filename="test.txt"),
            type=file_type,
            **target,
        )
    paths = [tmp_path / row.location for row in Files.query.all()]
    assert all(path.exists() for path in paths)
    assert len(get_all_challenges(admin=True)) == 2
    result = runner.invoke(
        args=["push-challenges", "delete", str(selected.id)], input="yes\n"
    )
    assert result.exit_code == 0, result.output
    assert Challenges.query.one().id == kept_id
    for model in (Submissions, Flags, Tags, Hints, Solutions, Files):
        assert model.query.count() == 0
    assert all(not path.exists() for path in paths)
    assert [row.id for row in get_all_challenges(admin=True)] == [kept_id]


def test_dynamic_deletion_uses_native_joined_table_cleanup(app, runner, monkeypatch):
    from CTFd.plugins.challenges import CHALLENGE_CLASSES
    from CTFd.plugins.dynamic_challenges import DynamicValueChallenge

    monkeypatch.setitem(CHALLENGE_CLASSES, "dynamic", DynamicValueChallenge)
    row = DynamicChallenge(
        name="Dynamic", type="dynamic", initial=100, minimum=10, decay=5
    )
    db.session.add(row)
    db.session.commit()
    result = runner.invoke(
        args=["push-challenges", "delete", str(row.id)], input="yes\n"
    )
    assert result.exit_code == 0, result.output
    assert Challenges.query.count() == DynamicChallenge.query.count() == 0


def test_failure_reports_id_and_continues_without_retrying(app, runner, monkeypatch):
    rows = [persisted_challenge(name) for name in ("First", "Blocked", "Last")]
    ids = [row.id for row in rows]
    native_delete = BaseChallenge.delete.__func__

    def fail_one(cls, challenge):
        if challenge.name == "Blocked":
            challenge.description = "must roll back"
            db.session.flush()
            raise RuntimeError("injected storage failure")
        native_delete(cls, challenge)

    monkeypatch.setattr(BaseChallenge, "delete", classmethod(fail_one))
    result = runner.invoke(
        args=["push-challenges", "delete", f"{ids[0]}-{ids[2]}"], input="yes\n"
    )
    assert result.exit_code != 0
    assert Challenges.query.one().id == ids[1]
    assert Challenges.query.one().description == "Existing"
    assert "deleted: 2" in result.output
    assert "failed: 1" in result.output
    assert f"FAILED: {ids[1]}" in result.output
    assert "injected storage failure" in result.output


def test_unknown_challenge_handler_aborts_before_any_deletion(app, runner):
    known = persisted_challenge("Known")
    db.session.execute(
        Challenges.__table__.insert().values(
            name="Unknown", type="unavailable", value=1, state="hidden"
        )
    )
    db.session.commit()
    unknown_id = db.session.query(db.func.max(Challenges.id)).scalar()
    result = runner.invoke(
        args=["push-challenges", "delete", f"{known.id},{unknown_id}"], input="yes\n"
    )
    assert result.exit_code != 0
    assert "unavailable" in result.output
    assert db.session.query(Challenges.id).count() == 2


def test_fifty_challenge_batch_removes_every_selected_id(app, runner):
    db.session.add_all(
        Challenges(name=f"Batch {index}", type="standard", value=10, state="hidden")
        for index in range(50)
    )
    db.session.commit()
    result = runner.invoke(args=["push-challenges", "delete", "1-50"], input="yes\n")
    assert result.exit_code == 0, result.output
    assert Challenges.query.count() == 0
    assert "deleted: 50; failed: 0" in result.output
    assert result.output.count("DELETED:") == 50


def test_changed_target_is_not_deleted_after_confirmation(app, runner, monkeypatch):
    import click

    challenge = persisted_challenge("Original")
    challenge_id = challenge.id
    solution = gen_solution(db, challenge_id=challenge_id)
    solution_id = solution.id
    prompt = click.prompt

    def rename_during_confirmation(*args, **kwargs):
        answer = prompt(*args, **kwargs)
        Challenges.query.filter_by(id=challenge_id).update({"name": "Changed"})
        db.session.commit()
        return answer

    monkeypatch.setattr(click, "prompt", rename_during_confirmation)
    result = runner.invoke(
        args=["push-challenges", "delete", str(challenge_id)], input="yes\n"
    )
    assert result.exit_code != 0
    assert Challenges.query.one().name == "Changed"
    assert Solutions.query.one().id == solution_id
    assert "changed since preview" in result.output


def test_cache_failure_does_not_hide_committed_deletion(app, runner, monkeypatch):
    from CTFd.utils.challenges import get_all_challenges

    maintenance = importlib.import_module("CTFd.plugins.push-challenges.maintenance")
    challenge = persisted_challenge("Remove")
    assert len(get_all_challenges(admin=True)) == 1

    def cache_failure():
        raise RuntimeError("injected cache failure")

    monkeypatch.setattr(maintenance, "clear_standings", cache_failure)
    result = runner.invoke(
        args=["push-challenges", "delete", str(challenge.id)], input="yes\n"
    )
    assert result.exit_code != 0
    assert Challenges.query.count() == 0
    assert "deleted: 1; failed: 0" in result.output
    assert "injected cache failure" in result.output
    assert "remain committed" in result.output
    assert get_all_challenges(admin=True) == []


@pytest.mark.parametrize("challenge_type", ["standard", "dynamic"])
def test_delete_removes_only_selected_solution_files_and_unlocks(
    app, runner, tmp_path, monkeypatch, challenge_type
):
    from CTFd.plugins.challenges import CHALLENGE_CLASSES
    from CTFd.plugins.dynamic_challenges import DynamicValueChallenge

    if challenge_type == "dynamic":
        monkeypatch.setitem(CHALLENGE_CLASSES, "dynamic", DynamicValueChallenge)
        selected = DynamicChallenge(
            name="Selected", type="dynamic", initial=100, minimum=10, decay=5
        )
        db.session.add(selected)
        db.session.commit()
    else:
        selected = persisted_challenge("Selected")
    selected_id = selected.id
    kept_id = persisted_challenge("Keep").id
    selected_solution_id = gen_solution(db, challenge_id=selected_id).id
    kept_solution_id = gen_solution(db, challenge_id=kept_id).id
    user_id = gen_user(db).id
    db.session.add_all(
        [
            SolutionUnlocks(user_id=user_id, target=selected_solution_id),
            SolutionUnlocks(user_id=user_id, target=kept_solution_id),
            HintUnlocks(user_id=user_id, target=selected_solution_id),
        ]
    )
    db.session.commit()
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    paths = []
    for solution_id in (selected_solution_id, kept_solution_id):
        row = upload_file(
            file=FileStorage(stream=io.BytesIO(b"solution"), filename="solution.txt"),
            type="solution",
            solution_id=solution_id,
        )
        paths.append(tmp_path / row.location)

    result = runner.invoke(
        args=["push-challenges", "delete", str(selected_id)], input="yes\n"
    )

    assert result.exit_code == 0, result.output
    assert Challenges.query.one().id == kept_id
    assert Solutions.query.one().id == kept_solution_id
    assert Files.query.one().solution_id == kept_solution_id
    assert SolutionUnlocks.query.one().target == kept_solution_id
    assert HintUnlocks.query.one().target == selected_solution_id
    assert not paths[0].exists()
    assert paths[1].read_bytes() == b"solution"
    assert "deleted: 1; failed: 0" in result.output


def test_solution_file_failure_preserves_failed_challenge_and_continues(
    app, runner, tmp_path, monkeypatch
):
    from CTFd.utils.uploads.uploaders import FilesystemUploader

    first_id = persisted_challenge("Blocked").id
    last_id = persisted_challenge("Delete").id
    solution_id = gen_solution(db, challenge_id=first_id).id
    app.config["UPLOAD_FOLDER"] = str(tmp_path)
    row = upload_file(
        file=FileStorage(stream=io.BytesIO(b"keep"), filename="solution.txt"),
        type="solution",
        solution_id=solution_id,
    )
    path = tmp_path / row.location

    def storage_failure(self, filename):
        raise OSError("injected solution storage failure")

    monkeypatch.setattr(FilesystemUploader, "delete", storage_failure)
    result = runner.invoke(
        args=["push-challenges", "delete", f"{first_id},{last_id}"], input="yes\n"
    )
    assert result.exit_code != 0
    assert "injected solution storage failure" in result.output
    assert "deleted: 1; failed: 1" in result.output
    assert Challenges.query.one().id == first_id
    assert Solutions.query.one().id == solution_id
    assert Files.query.one().solution_id == solution_id
    assert path.read_bytes() == b"keep"


def test_native_failure_rolls_back_uncommitted_solution_cleanup(
    app, runner, monkeypatch
):
    challenge_id = persisted_challenge("Blocked").id
    solution_id = gen_solution(db, challenge_id=challenge_id).id
    user_id = gen_user(db).id
    db.session.add(SolutionUnlocks(user_id=user_id, target=solution_id))
    db.session.commit()

    def native_failure(cls, challenge):
        raise RuntimeError("injected native failure")

    monkeypatch.setattr(BaseChallenge, "delete", classmethod(native_failure))
    result = runner.invoke(
        args=["push-challenges", "delete", str(challenge_id)], input="yes\n"
    )
    assert result.exit_code != 0
    assert "injected native failure" in result.output
    assert Challenges.query.one().id == challenge_id
    assert Solutions.query.one().id == solution_id
    assert SolutionUnlocks.query.one().target == solution_id
