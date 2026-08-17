import json

from push_challenges_core.manifest import (
    dump_manifest,
    load_manifest,
    validate_manifest_data,
)


def valid_manifest_data():
    return {
        "format": "push-challenges",
        "version": 1,
        "warnings": [],
        "challenges": [
            {
                "name": "Example",
                "description": "Challenge text",
                "value": 100,
                "category": "Web",
                "state": "hidden",
                "type": "standard",
                "logic": "any",
                "max_attempts": 0,
                "attribution": "",
                "connection_info": "",
                "tags": ["beginner", "web authentication"],
                "next": None,
                "solution": {
                    "action": "upsert",
                    "content": "An example solution",
                    "state": "hidden",
                },
                "flags": [
                    {
                        "type": "static",
                        "content": "flag{example}",
                        "data": "case_sensitive",
                    }
                ],
                "hints": [
                    {
                        "title": "First clue",
                        "content": "Look at the headers.",
                        "cost": 10,
                        "required_hints": [],
                    }
                ],
            }
        ],
    }


def diagnostic_pairs(diagnostics):
    return {(item.code, item.source) for item in diagnostics}


def test_manifest_rejects_unknown_challenge_property():
    data = valid_manifest_data()
    data["challenges"][0]["mystery"] = True

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is None
    assert ("unknown_property", "challenges[0].mystery") in diagnostic_pairs(
        diagnostics
    )


def test_flagless_manifest_normalizes_logic_to_any():
    data = valid_manifest_data()
    data["challenges"][0]["flags"] = []
    data["challenges"][0]["logic"] = "all"

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is not None
    assert manifest.challenges[0].logic == "any"
    assert any(item.code == "flagless_logic_normalized" for item in diagnostics)


def test_manifest_round_trip_is_stable_pretty_json(tmp_path):
    manifest, diagnostics = validate_manifest_data(valid_manifest_data())
    assert manifest is not None
    assert diagnostics == ()
    first = tmp_path / "first.push.json"
    second = tmp_path / "second.push.json"

    dump_manifest(manifest, first)
    loaded = load_manifest(first)
    dump_manifest(loaded, second)

    assert first.read_bytes() == second.read_bytes()
    assert first.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(first.read_text(encoding="utf-8"))["version"] == 1


def test_manifest_preserves_nonblocking_authoring_warning():
    data = valid_manifest_data()
    data["warnings"] = [
        {
            "code": "orphan_hint_ignored",
            "message": "No matching challenge",
            "source": "Hints!A8",
            "blocking": False,
        }
    ]

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is not None
    assert diagnostics == ()
    assert manifest.warnings[0].code == "orphan_hint_ignored"
    assert manifest.warnings[0].blocking is False


def test_manifest_rejects_dynamic_as_recognized_but_unsupported():
    data = valid_manifest_data()
    data["challenges"][0]["type"] = "dynamic"

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is None
    assert ("unsupported_challenge_type", "challenges[0].type") in diagnostic_pairs(
        diagnostics
    )


def test_manifest_rejects_duplicate_names_and_hint_titles():
    data = valid_manifest_data()
    duplicate = dict(data["challenges"][0])
    duplicate["flags"] = []
    duplicate["hints"] = []
    data["challenges"].append(duplicate)
    data["challenges"][0]["hints"].append(
        {
            "title": "First clue",
            "content": "Again",
            "cost": 0,
            "required_hints": [],
        }
    )

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is None
    assert any(item.code == "duplicate_challenge_name" for item in diagnostics)
    assert any(item.code == "duplicate_hint_title" for item in diagnostics)


def test_manifest_enforces_ctfd_string_lengths_and_nonnegative_counts():
    data = valid_manifest_data()
    challenge = data["challenges"][0]
    challenge["name"] = "n" * 81
    challenge["category"] = "c" * 81
    challenge["description"] = "d" * 65536
    challenge["tags"] = ["t" * 81]
    challenge["max_attempts"] = -1
    challenge["hints"][0]["title"] = "h" * 81
    challenge["hints"][0]["cost"] = -5

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is None
    sources = {item.source for item in diagnostics}
    assert {
        "challenges[0].name",
        "challenges[0].category",
        "challenges[0].description",
        "challenges[0].tags[0]",
        "challenges[0].max_attempts",
        "challenges[0].hints[0].title",
        "challenges[0].hints[0].cost",
    } <= sources


def test_manifest_rejects_solution_and_flag_invariants():
    data = valid_manifest_data()
    challenge = data["challenges"][0]
    challenge["solution"] = {
        "action": "preserve",
        "content": "must not be present",
        "state": "visible",
    }
    challenge["flags"][0]["data"] = "sometimes"

    manifest, diagnostics = validate_manifest_data(data)

    assert manifest is None
    assert any(item.source == "challenges[0].solution.content" for item in diagnostics)
    assert any(item.source == "challenges[0].flags[0].data" for item in diagnostics)
