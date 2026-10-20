import copy
import json

import pytest
from test_manifest import valid_manifest_data

from push_challenges_core.manifest import (
    dump_manifest,
    load_manifest,
    validate_manifest_data,
)


def scoring_manifest():
    data = valid_manifest_data()
    data["version"] = 2
    challenge = data["challenges"][0]
    challenge["type"] = "dynamic"
    challenge["scoring"] = {"function": "linear", "minimum": 10, "decay": 5}
    challenge["bonus"] = {
        "mode": "percentage",
        "tiers": [
            {"start": 1, "end": 1, "amount": "25.999"},
            {"start": 2, "end": 5, "amount": "0"},
        ],
    }
    return data


def test_dynamic_and_bonus_manifest_round_trip(tmp_path):
    manifest, diagnostics = validate_manifest_data(scoring_manifest())
    assert manifest is not None, diagnostics
    spec = manifest.challenges[0]
    assert spec.scoring.function == "linear"
    assert spec.bonus.tiers[0].amount == "25.99"
    path = tmp_path / "v2.json"
    dump_manifest(manifest, path)
    assert load_manifest(path) == manifest
    assert json.loads(path.read_text())["version"] == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("function", "unknown"),
        ("minimum", 101),
        ("minimum", -1),
        ("decay", 0),
        ("decay", True),
        ("decay", 2.5),
    ],
)
def test_invalid_dynamic_scoring_blocks_manifest(field, value):
    data = scoring_manifest()
    data["challenges"][0]["scoring"][field] = value
    manifest, diagnostics = validate_manifest_data(data)
    assert manifest is None
    assert any(item.blocking for item in diagnostics)


@pytest.mark.parametrize(
    "tiers",
    [
        [],
        [{"start": 2, "end": 3, "amount": "10"}],
        [{"start": 1, "end": 2, "amount": "10"}, {"start": 2, "end": 3, "amount": "5"}],
        [{"start": 1, "end": 1, "amount": "-1"}],
        [{"start": 1, "end": 1, "amount": "NaN"}],
        [{"start": 1, "end": 1, "amount": "Infinity"}],
    ],
)
def test_invalid_bonus_blocks_manifest(tiers):
    data = scoring_manifest()
    data["challenges"][0]["bonus"]["tiers"] = tiers
    assert validate_manifest_data(data)[0] is None


def test_legacy_manifest_keeps_version_and_preserves_bonus(tmp_path):
    manifest, diagnostics = validate_manifest_data(valid_manifest_data())
    assert manifest is not None, diagnostics
    assert manifest.challenges[0].scoring is None
    assert manifest.challenges[0].bonus.mode == "preserve"
    path = tmp_path / "v1.json"
    dump_manifest(manifest, path)
    assert load_manifest(path) == manifest
    assert "bonus" not in json.loads(path.read_text())["challenges"][0]


def test_absolute_bonus_rejects_fractional_points_and_preserve_rejects_tiers():
    data = scoring_manifest()
    data["challenges"][0]["bonus"]["mode"] = "absolute"
    assert validate_manifest_data(data)[0] is None
    data = copy.deepcopy(data)
    data["challenges"][0]["bonus"]["mode"] = "preserve"
    assert validate_manifest_data(data)[0] is None
