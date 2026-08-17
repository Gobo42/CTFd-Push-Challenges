import importlib
import warnings

from conftest import challenge_data, manifest_data
from CTFd.models import (
    ChallengeFiles,
    Challenges,
    Flags,
    Hints,
    HintUnlocks,
    SolutionFiles,
    Solutions,
    Tags,
    db,
)
from sqlalchemy import event
from sqlalchemy.exc import SAWarning

from push_challenges_core.manifest import validate_manifest_data


def importer_module():
    return importlib.import_module("CTFd.plugins.push-challenges.importer")


def canonical_manifest(*challenges):
    manifest, diagnostics = validate_manifest_data(manifest_data(*challenges))
    assert manifest is not None, diagnostics
    return manifest


def test_apply_inserts_static_and_regex_flags_without_polymorphic_warning(app):
    challenge = challenge_data("Warning-free flags")
    challenge["flags"] = [
        {
            "type": "static",
            "content": "flag{static}",
            "data": "case_sensitive",
        },
        {
            "type": "regex",
            "content": r"flag\{.*\}",
            "data": "case_insensitive",
        },
    ]
    importer = importer_module()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", SAWarning)
        result = importer.apply_plan(
            importer.build_plan(canonical_manifest(challenge))
        )

    polymorphic = tuple(
        warning
        for warning in captured
        if "incompatible polymorphic identity" in str(warning.message)
    )
    assert polymorphic == ()
    assert result.committed is True
    stored = Flags.query.order_by(Flags.id).all()
    assert tuple((flag.type, flag.content, flag.data) for flag in stored) == (
        ("static", "flag{static}", "case_sensitive"),
        ("regex", r"flag\{.*\}", "case_insensitive"),
    )


def test_apply_creates_linked_standard_challenges_with_replacements(app):
    first = challenge_data("First", next_name="Second")
    first.update(
        {
            "description": "New prompt",
            "value": -10,
            "category": "Intro",
            "state": "visible",
            "logic": "all",
            "max_attempts": 2,
            "attribution": "Author",
            "connection_info": "nc host 31337",
            "tags": ["beginner", "network"],
            "flags": [
                {
                    "type": "static",
                    "content": "flag{x}",
                    "data": "case_sensitive",
                },
                {
                    "type": "regex",
                    "content": r"flag\{.*\}",
                    "data": "case_insensitive",
                },
            ],
        }
    )
    second = challenge_data("Second")
    importer = importer_module()
    plan = importer.build_plan(canonical_manifest(first, second))
    commit_count = 0

    def count_commit(session):
        nonlocal commit_count
        commit_count += 1

    session = db.session()
    event.listen(session, "after_commit", count_commit)
    try:
        result = importer.apply_plan(plan)
    finally:
        event.remove(session, "after_commit", count_commit)

    assert result.committed is True
    assert result.cache_warnings == ()
    assert commit_count == 1
    linked = Challenges.query.filter_by(name="First").one()
    target = Challenges.query.filter_by(name="Second").one()
    assert linked.next_id == target.id
    assert linked.function == "static"
    assert linked.value == -10
    assert linked.max_attempts == 2
    assert linked.attribution == "Author"
    assert linked.connection_info == "nc host 31337"
    assert tuple(tag.value for tag in linked.tags) == ("beginner", "network")
    assert tuple((flag.type, flag.data) for flag in linked.flags) == (
        ("static", "case_sensitive"),
        ("regex", "case_insensitive"),
    )


def test_overwrite_preserves_files_solution_hint_ids_unlocks_and_omitted_hints(
    app,
):
    challenge = Challenges(
        name="Example",
        description="Old prompt",
        value=50,
        category="Old",
        state="visible",
        type="standard",
        function="static",
        logic="any",
        max_attempts=9,
        attribution="Old author",
        connection_info="old host",
    )
    db.session.add(challenge)
    db.session.flush()
    old_flag = Flags(
        challenge_id=challenge.id,
        type="static",
        content="old",
        data="case_sensitive",
    )
    old_tag = Tags(challenge_id=challenge.id, value="old")
    challenge_file = ChallengeFiles(
        challenge_id=challenge.id, location="challenge/file.txt"
    )
    solution = Solutions(
        challenge_id=challenge.id, content="Old solution", state="visible"
    )
    db.session.add_all((old_flag, old_tag, challenge_file, solution))
    db.session.flush()
    solution_file = SolutionFiles(
        solution_id=solution.id, location="solution/file.txt"
    )
    updated_hint = Hints(
        challenge_id=challenge.id,
        title="Update me",
        content="Old hint",
        cost=1,
        requirements=None,
        type="standard",
    )
    omitted_hint = Hints(
        challenge_id=challenge.id,
        title="Keep me",
        content="Untouched",
        cost=2,
        requirements={"prerequisites": []},
        type="standard",
    )
    db.session.add_all((solution_file, updated_hint, omitted_hint))
    db.session.flush()
    unlock = HintUnlocks(user_id=1, target=updated_hint.id, type="hints")
    db.session.add(unlock)
    db.session.commit()
    retained = {
        "challenge_file": challenge_file.id,
        "solution": solution.id,
        "solution_file": solution_file.id,
        "updated_hint": updated_hint.id,
        "omitted_hint": omitted_hint.id,
        "unlock": unlock.id,
    }

    imported = challenge_data("Example")
    imported.update(
        {
            "description": "New prompt",
            "category": "Web",
            "max_attempts": 0,
            "attribution": "",
            "connection_info": "",
            "tags": ["new"],
            "flags": [
                {
                    "type": "regex",
                    "content": "^new$",
                    "data": "case_insensitive",
                }
            ],
            "solution": {
                "action": "upsert",
                "content": "New solution",
                "state": "solved",
            },
            "hints": [
                {
                    "title": "Update me",
                    "content": "New hint",
                    "cost": 5,
                    "required_hints": [],
                },
                {
                    "title": "New hint",
                    "content": "Created",
                    "cost": 10,
                    "required_hints": ["Update me"],
                },
            ],
        }
    )
    importer = importer_module()

    importer.apply_plan(importer.build_plan(canonical_manifest(imported)))

    refreshed = Challenges.query.filter_by(name="Example").one()
    assert refreshed.description == "New prompt"
    assert refreshed.attribution == ""
    assert refreshed.connection_info == ""
    assert tuple(tag.value for tag in refreshed.tags) == ("new",)
    assert tuple(flag.content for flag in refreshed.flags) == ("^new$",)
    assert ChallengeFiles.query.get(retained["challenge_file"]) is not None
    assert refreshed.solution.id == retained["solution"]
    assert refreshed.solution.content == "New solution"
    assert refreshed.solution.state == "solved"
    assert SolutionFiles.query.get(retained["solution_file"]) is not None
    assert Hints.query.get(retained["updated_hint"]).content == "New hint"
    assert Hints.query.get(retained["omitted_hint"]).content == "Untouched"
    assert HintUnlocks.query.get(retained["unlock"]).target == retained["updated_hint"]
    created = Hints.query.filter_by(
        challenge_id=refreshed.id, title="New hint"
    ).one()
    assert created.requirements == {
        "prerequisites": [retained["updated_hint"]]
    }
    assert Flags.query.filter_by(
        challenge_id=refreshed.id, content="old"
    ).count() == 0
    assert Tags.query.filter_by(
        challenge_id=refreshed.id, value="old"
    ).count() == 0

    clear = challenge_data("Example")
    clear["solution"] = {"action": "clear", "content": None, "state": None}
    importer.apply_plan(importer.build_plan(canonical_manifest(clear)))

    retained_solution = Solutions.query.get(retained["solution"])
    assert retained_solution.content == ""
    assert retained_solution.state == "hidden"
    assert SolutionFiles.query.get(retained["solution_file"]) is not None


def test_cache_failure_is_post_commit_warning_not_rollback(app, monkeypatch):
    importer = importer_module()
    plan = importer.build_plan(canonical_manifest(challenge_data("Committed")))

    def fail_cache():
        raise RuntimeError("cache backend unavailable")

    monkeypatch.setattr(importer, "clear_challenges", fail_cache)
    result = importer.apply_plan(plan)

    assert result.committed is True
    assert result.cache_warnings == (
        "clear_challenges: cache backend unavailable",
    )
    assert Challenges.query.filter_by(name="Committed").one() is not None
