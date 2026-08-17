import importlib

import pytest
from conftest import challenge_data, manifest_data
from CTFd.models import Challenges, Hints, db

from push_challenges_core.manifest import validate_manifest_data


def persisted_challenge(name, *, next_id=None, challenge_type="standard"):
    challenge = Challenges(
        name=name,
        description="Existing",
        value=50,
        category="Old",
        state="visible",
        type=challenge_type,
        function="static",
        next_id=next_id,
    )
    db.session.add(challenge)
    db.session.commit()
    return challenge


def canonical_manifest(*challenges):
    manifest, diagnostics = validate_manifest_data(manifest_data(*challenges))
    assert manifest is not None, diagnostics
    return manifest


def importer_module():
    return importlib.import_module("CTFd.plugins.push-challenges.importer")


def test_preflight_classifies_exact_name_create_and_overwrite(app):
    persisted = persisted_challenge("Existing")
    build_plan = importer_module().build_plan

    plan = build_plan(
        canonical_manifest(challenge_data("Existing"), challenge_data("New"))
    )

    assert tuple(action.mode for action in plan.challenges) == (
        "overwrite",
        "create",
    )
    assert plan.challenges[0].existing_id == persisted.id
    assert plan.challenges[1].existing_id is None


def test_preflight_resolves_external_existing_next_target(app):
    target = persisted_challenge("Existing Target")
    build_plan = importer_module().build_plan

    plan = build_plan(
        canonical_manifest(challenge_data("New", next_name="Existing Target"))
    )

    assert plan.projected_next["New"] == "Existing Target"
    assert target.id is not None


def test_projected_cycle_crossing_database_aborts(app):
    imported = persisted_challenge("A")
    existing = persisted_challenge("Existing", next_id=imported.id)
    importer = importer_module()

    with pytest.raises(
        importer.ImportPreflightError, match="A -> Existing -> A"
    ):
        importer.build_plan(
            canonical_manifest(challenge_data("A", next_name="Existing"))
        )

    assert existing.next_id == imported.id


def test_duplicate_relevant_database_name_aborts_with_ids(app):
    first = persisted_challenge("Duplicate")
    second = persisted_challenge("Duplicate")
    importer = importer_module()

    with pytest.raises(importer.ImportPreflightError) as caught:
        importer.build_plan(canonical_manifest(challenge_data("Duplicate")))

    assert str(first.id) in str(caught.value)
    assert str(second.id) in str(caught.value)


@pytest.mark.parametrize(
    ("challenge_type", "function"),
    [("dynamic", "static"), ("standard", "decay")],
)
def test_unsupported_overwrite_target_aborts(app, challenge_type, function):
    challenge = persisted_challenge("Example", challenge_type=challenge_type)
    challenge.function = function
    db.session.commit()
    importer = importer_module()

    with pytest.raises(
        importer.ImportPreflightError, match="fixed-value standard"
    ):
        importer.build_plan(canonical_manifest(challenge_data("Example")))


def test_exact_hint_title_is_classified_as_in_place_update(app):
    challenge = persisted_challenge("Example")
    hint = Hints(
        challenge_id=challenge.id,
        title="Clue",
        content="Old",
        cost=0,
        type="standard",
    )
    db.session.add(hint)
    db.session.commit()
    imported = challenge_data("Example")
    imported["hints"] = [
        {
            "title": "Clue",
            "content": "New",
            "cost": 5,
            "required_hints": [],
        }
    ]
    build_plan = importer_module().build_plan

    plan = build_plan(canonical_manifest(imported))

    assert plan.hints[0].mode == "update"
    assert plan.hints[0].existing_id == hint.id


def test_ambiguous_existing_hint_title_aborts_with_ids(app):
    challenge = persisted_challenge("Example")
    hints = [
        Hints(
            challenge_id=challenge.id,
            title="Clue",
            content=str(index),
            cost=0,
            type="standard",
        )
        for index in range(2)
    ]
    db.session.add_all(hints)
    db.session.commit()
    imported = challenge_data("Example")
    imported["hints"] = [
        {
            "title": "Clue",
            "content": "New",
            "cost": 0,
            "required_hints": [],
        }
    ]
    importer = importer_module()

    with pytest.raises(importer.ImportPreflightError) as caught:
        importer.build_plan(canonical_manifest(imported))

    assert str(hints[0].id) in str(caught.value)
    assert str(hints[1].id) in str(caught.value)
