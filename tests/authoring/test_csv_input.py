from pathlib import Path

from authoring.csv_input import CSV_HEADERS, load_csv


def test_csv_accepts_excel_bom_crlf_and_multiline_description(tmp_path):
    path = tmp_path / "excel.csv"
    header = ",".join(CSV_HEADERS)
    content = (
        "\ufeff"
        + header
        + '\r\nExample,"Line one\r\nLine two",100,Web,Hidden,Standard,'
        + "#beginner,,Require Any Flag,0,,,,Hidden,[],[]\r\n"
    )
    path.write_text(content, encoding="utf-8", newline="")

    document = load_csv(path)

    assert document.diagnostics == ()
    assert len(document.rows) == 1
    assert document.rows[0].source == "CSV row 2"
    assert document.rows[0].values["Description"] == "Line one\r\nLine two"


def test_csv_rejects_header_typo_before_returning_rows(tmp_path):
    path = tmp_path / "bad.csv"
    headers = list(CSV_HEADERS)
    headers[2] = "Points"
    path.write_text(",".join(headers) + "\n", encoding="utf-8")

    document = load_csv(path)

    assert document.rows == ()
    assert any(item.code == "invalid_csv_headers" for item in document.diagnostics)
    assert document.diagnostics[0].blocking is True


def test_csv_rejects_duplicate_headers(tmp_path):
    path = tmp_path / "duplicate.csv"
    headers = list(CSV_HEADERS)
    headers[-1] = "Flags"
    path.write_text(",".join(headers) + "\n", encoding="utf-8")

    document = load_csv(path)

    assert document.rows == ()
    assert "duplicate" in document.diagnostics[0].message.lower()


def test_committed_valid_fixture_has_two_challenges():
    path = Path(__file__).parents[1] / "fixtures" / "valid-challenges.csv"

    document = load_csv(path)

    assert document.diagnostics == ()
    assert tuple(row.values["Name"] for row in document.rows) == (
        "Welcome",
        "Second",
    )
