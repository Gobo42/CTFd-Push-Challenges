import json

import pytest
from test_manifest import valid_manifest_data

from push_challenges_core.manifest import (
    dump_manifest,
    load_manifest,
    validate_manifest_data,
)


def position_data(position=None):
    data = valid_manifest_data()
    data["version"] = 2
    data["challenges"][0].update(
        scoring=None, bonus={"mode": "preserve", "tiers": []}, position=position
    )
    return data


@pytest.mark.parametrize("position", [None, 0, 10, 2_147_483_647])
def test_position_survives_manifest_round_trip(tmp_path, position):
    manifest, diagnostics = validate_manifest_data(position_data(position))
    assert manifest is not None, diagnostics
    assert manifest.challenges[0].position == position
    path = tmp_path / "position.json"
    dump_manifest(manifest, path)
    assert json.loads(path.read_text())["challenges"][0]["position"] == position
    assert load_manifest(path) == manifest


@pytest.mark.parametrize("position", [-1, 2_147_483_648, True, 1.5, "10", ""])
def test_invalid_canonical_position_blocks_manifest(position):
    manifest, diagnostics = validate_manifest_data(position_data(position))
    assert manifest is None
    assert any(
        item.source == "challenges[0].position" and item.blocking
        for item in diagnostics
    )


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_manifest_preserves_position_intent(tmp_path, version):
    data = position_data()
    del data["challenges"][0]["position"]
    if version == 1:
        data["version"] = 1
        del data["challenges"][0]["scoring"]
        del data["challenges"][0]["bonus"]
    manifest, diagnostics = validate_manifest_data(data)
    assert manifest is not None, diagnostics
    assert manifest.challenges[0].position is None
    path = tmp_path / "legacy.json"
    dump_manifest(manifest, path)
    assert load_manifest(path) == manifest
    if version == 1:
        assert "position" not in json.loads(path.read_text())["challenges"][0]
