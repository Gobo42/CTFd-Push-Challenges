import importlib

import pytest
from conftest import challenge_data, manifest_data
from CTFd.models import Challenges, Flags, Tags, db

from push_challenges_core.manifest import validate_manifest_data


def importer_module():
    return importlib.import_module("CTFd.plugins.push-challenges.importer")


def canonical_manifest(*challenges):
    manifest, diagnostics = validate_manifest_data(manifest_data(*challenges))
    assert manifest is not None, diagnostics
    return manifest


def snapshot_database():
    return {
        "challenges": tuple(
            (row.id, row.name, row.description, row.value, row.next_id)
            for row in Challenges.query.order_by(Challenges.id)
        ),
        "flags": tuple(
            (row.id, row.challenge_id, row.type, row.content, row.data)
            for row in Flags.query.order_by(Flags.id)
        ),
        "tags": tuple(
            (row.id, row.challenge_id, row.value)
            for row in Tags.query.order_by(Tags.id)
        ),
    }


def test_mid_apply_failure_rolls_back_every_change(app):
    existing = Challenges(
        name="Existing",
        description="Before",
        value=50,
        category="Old",
        state="visible",
        type="standard",
        function="static",
    )
    db.session.add(existing)
    db.session.flush()
    db.session.add_all(
        (
            Flags(
                challenge_id=existing.id,
                type="static",
                content="old",
                data="case_sensitive",
            ),
            Tags(challenge_id=existing.id, value="old"),
        )
    )
    db.session.commit()
    before = snapshot_database()
    changed = challenge_data("Existing")
    changed["description"] = "After"
    changed["flags"] = [
        {
            "type": "static",
            "content": "new",
            "data": "case_sensitive",
        }
    ]
    changed["tags"] = ["new"]
    importer = importer_module()
    plan = importer.build_plan(
        canonical_manifest(changed, challenge_data("New"))
    )

    def fail_after_hints(stage):
        if stage == "after_hints":
            raise RuntimeError("injected failure")

    with pytest.raises(
        importer.ImportApplyError, match="transaction was rolled back"
    ):
        importer.apply_plan(plan, stage_hook=fail_after_hints)

    assert snapshot_database() == before
