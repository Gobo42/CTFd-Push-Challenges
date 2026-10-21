from dataclasses import replace

import pytest
from conftest import challenge_data
from CTFd.models import Challenges, db
from test_preflight import importer_module, persisted_challenge
from test_scoring_import import scoring_data, scoring_manifest


@pytest.mark.parametrize("challenge_type", ["standard", "dynamic"])
def test_position_updates_preserves_and_clears(app, challenge_type):
    importer = importer_module()
    data = (
        scoring_data("Ordered")
        if challenge_type == "dynamic"
        else challenge_data("Ordered")
    )
    manifest = scoring_manifest(data)
    manifest = replace(
        manifest, challenges=(replace(manifest.challenges[0], position=30),)
    )
    importer.apply_plan(importer.build_plan(manifest))
    stored = Challenges.query.one()
    assert stored.position == 30
    for position, expected in ((None, 30), (10, 10), (0, 0)):
        changed = replace(
            manifest, challenges=(replace(manifest.challenges[0], position=position),)
        )
        plan = importer.build_plan(changed)
        output = importer.render_plan(plan)
        assert "Position:" in output
        importer.apply_plan(plan)
        assert stored.position == expected


def test_position_changes_roll_back_with_import(app):
    importer = importer_module()
    existing = persisted_challenge("Existing")
    existing.position = 40
    db.session.commit()
    manifest = scoring_manifest(challenge_data("Existing"))
    manifest = replace(
        manifest, challenges=(replace(manifest.challenges[0], position=10),)
    )

    def fail(stage):
        if stage == "after_next":
            raise RuntimeError("injected failure")

    with pytest.raises(importer.ImportApplyError, match="rolled back"):
        importer.apply_plan(importer.build_plan(manifest), stage_hook=fail)
    assert existing.position == 40


def test_absent_position_preserves_existing_and_defaults_new(app):
    importer = importer_module()
    existing = persisted_challenge("Existing")
    existing.position = 40
    db.session.commit()
    manifest = scoring_manifest(challenge_data("Existing"), challenge_data("New"))
    plan = importer.build_plan(manifest)
    assert all("position" not in action.changes for action in plan.challenges)
    importer.apply_plan(plan)
    assert existing.position == 40
    assert Challenges.query.filter_by(name="New").one().position == 0


def test_skipped_challenge_preserves_position(app):
    importer = importer_module()
    existing = persisted_challenge("Existing")
    existing.position = 40
    db.session.commit()
    data = scoring_data("Existing")
    data["position"] = 10
    plan = importer.build_plan(scoring_manifest(data))
    assert len(plan.skipped) == 1
    importer.apply_plan(plan)
    assert existing.position == 40


def test_imported_positions_control_native_order_before_point_value(app):
    from CTFd.utils.challenges import get_all_challenges

    importer = importer_module()
    first = challenge_data("A 1/2")
    first.update(value=200, position=10)
    second = challenge_data("A 2/2")
    second.update(value=100, position=20)
    automatic = challenge_data("Automatic")
    automatic.update(value=1, position=0)
    importer.apply_plan(importer.build_plan(scoring_manifest(automatic, second, first)))
    assert [item.name for item in get_all_challenges(admin=True)] == [
        "A 1/2",
        "A 2/2",
        "Automatic",
    ]
