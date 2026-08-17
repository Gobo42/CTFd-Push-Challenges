import csv
import json

from authoring.csv_input import CSV_HEADERS, load_csv
from authoring.normalize import normalize
from authoring.preview import render_preview
from tools.validate_challenges import main


def write_csv(tmp_path, **overrides):
    row = {
        "Name": "Example",
        "Description": "Prompt",
        "Value": "100",
        "Category": "Web",
        "State": "Hidden",
        "Type": "Standard",
        "Tags": "#beginner #web authentication",
        "Next": "",
        "Logic": "Require Any Flag",
        "Max Attempts": "0",
        "Attribution": "",
        "Connection Info": "",
        "Solution": "",
        "Solution State": "",
        "Flags": json.dumps(
            [
                {
                    "type": "static",
                    "content": "flag{x}",
                    "data": "case_sensitive",
                }
            ]
        ),
        "Hints": json.dumps(
            [
                {
                    "title": "Clue",
                    "content": "Read it",
                    "cost": 5,
                    "required_hints": [],
                }
            ]
        ),
    }
    row.update(overrides)
    path = tmp_path / "preview.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerow(row)
    return path


def test_csv_preview_decodes_nested_fields(tmp_path):
    result = normalize(load_csv(write_csv(tmp_path)))

    output = render_preview(result)

    assert "Tags: beginner; web authentication" in output
    assert "Static / Case Sensitive: flag{x}" in output
    assert "Hint 1: Clue (cost 5)" in output


def test_validator_cli_writes_manifest_only_on_success(tmp_path, capsys):
    source = write_csv(tmp_path)
    output = tmp_path / "challenges.push.json"

    exit_code = main([str(source), "--output", str(output)])

    assert exit_code == 0
    assert output.exists()
    assert "Example" in capsys.readouterr().out


def test_validator_cli_does_not_write_manifest_on_blocking_error(
    tmp_path, capsys
):
    source = write_csv(tmp_path, Value="one hundred")
    output = tmp_path / "challenges.push.json"

    exit_code = main([str(source), "--output", str(output)])

    assert exit_code != 0
    assert not output.exists()
    assert "ERROR" in capsys.readouterr().out
