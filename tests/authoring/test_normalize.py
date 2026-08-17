import csv
import json

from authoring.csv_input import CSV_HEADERS, load_csv
from authoring.normalize import normalize


def write_csv(tmp_path, **overrides):
    values = {
        "Name": "Example",
        "Description": "",
        "Value": "100",
        "Category": "Web",
        "State": "",
        "Type": "Standard",
        "Tags": "#beginner #web authentication",
        "Next": "",
        "Logic": "",
        "Max Attempts": "0",
        "Attribution": "",
        "Connection Info": "",
        "Solution": "",
        "Solution State": "",
        "Flags": "[]",
        "Hints": "[]",
    }
    values.update(overrides)
    path = tmp_path / "challenges.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerow(values)
    return path


def test_csv_defaults_and_hash_tags_normalize_to_manifest(tmp_path):
    result = normalize(load_csv(write_csv(tmp_path)))

    assert result.manifest is not None
    challenge = result.manifest.challenges[0]
    assert challenge.state == "hidden"
    assert challenge.logic == "any"
    assert challenge.max_attempts == 0
    assert challenge.tags == ("beginner", "web authentication")
    assert challenge.solution.action == "preserve"


def test_csv_decodes_flags_hints_and_remove_solution(tmp_path):
    flags = json.dumps(
        [
            {
                "type": "regex",
                "content": r"flag\{.*\}",
                "data": "case_insensitive",
            }
        ]
    )
    hints = json.dumps(
        [
            {
                "title": "First",
                "content": "Read it",
                "cost": 0,
                "required_hints": [],
            },
            {
                "title": "Second",
                "content": "Decode it",
                "cost": 5,
                "required_hints": [1],
            },
        ]
    )
    source = write_csv(
        tmp_path,
        Flags=flags,
        Hints=hints,
        Solution="REMOVE",
        **{"Solution State": "Solved"},
    )

    result = normalize(load_csv(source))

    assert result.manifest is not None
    challenge = result.manifest.challenges[0]
    assert challenge.flags[0].type == "regex"
    assert challenge.flags[0].data == "case_insensitive"
    assert challenge.hints[1].required_hints == ("First",)
    assert challenge.solution.action == "clear"
    assert challenge.solution.state is None


def test_bad_required_hint_is_warning_and_manifest_is_still_emitted(tmp_path):
    hints = json.dumps(
        [
            {
                "title": "First",
                "content": "Read it",
                "cost": 0,
                "required_hints": [2],
            }
        ]
    )

    result = normalize(load_csv(write_csv(tmp_path, Hints=hints)))

    assert result.manifest is not None
    assert result.manifest.challenges[0].hints[0].required_hints == ()
    assert result.manifest.warnings[0].code == "hint_requirements_ignored"
    assert result.manifest.warnings[0].blocking is False


def test_local_next_cycle_blocks_manifest(tmp_path):
    first = {
        "Name": "A",
        "Description": "",
        "Value": "100",
        "Category": "Web",
        "State": "Hidden",
        "Type": "Standard",
        "Tags": "",
        "Next": "B",
        "Logic": "Require Any Flag",
        "Max Attempts": "0",
        "Attribution": "",
        "Connection Info": "",
        "Solution": "",
        "Solution State": "",
        "Flags": "[]",
        "Hints": "[]",
    }
    second = dict(first, Name="B", Next="A")
    path = tmp_path / "cycle.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows((first, second))

    result = normalize(load_csv(path))

    assert result.manifest is None
    assert any(item.code == "circular_next_chain" for item in result.diagnostics)


def test_dynamic_and_malformed_nested_json_are_blocking(tmp_path):
    source = write_csv(tmp_path, Type="Dynamic", Flags="{not-json")

    result = normalize(load_csv(source))

    assert result.manifest is None
    codes = {item.code for item in result.diagnostics}
    assert "unsupported_challenge_type" in codes
    assert "invalid_flags_json" in codes
