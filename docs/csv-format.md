# CSV Format

The standalone validator accepts UTF-8 CSV, including an Excel UTF-8 BOM, CRLF
line endings, and quoted multiline descriptions.

The exact header sequence is:

```text
Name,Description,Value,Category,State,Type,Tags,Next,Logic,Max Attempts,Attribution,Connection Info,Solution,Solution State,Flags,Hints
```

Unknown, missing, reordered, or duplicate headers are errors.

Required values are Name, Value, Category, Type, and Max Attempts. Description
may be blank. State defaults to Hidden and Logic defaults to Require Any Flag.
Max Attempts must be a nonnegative whole number; `0` means unlimited.
Attribution and Connection Info may be blank and are explicitly cleared on
overwrite.

Tags use the same hash syntax as the workbook:

```text
#beginner #web authentication #SQL injection
```

That value decodes to `beginner`, `web authentication`, and `SQL injection`.

## Flags column

Flags is blank or a JSON array:

```json
[
  {
    "type": "static",
    "content": "flag{example}",
    "data": "case_sensitive"
  },
  {
    "type": "regex",
    "content": "flag\\{.*\\}",
    "data": "case_insensitive"
  }
]
```

Supported type values are `static` and `regex`. Matching data is
`case_sensitive` or `case_insensitive`. The JSON text must be correctly quoted
as one CSV cell. Empty flags are allowed.

## Solution columns

- Blank Solution preserves an existing solution.
- Text upserts the solution; blank Solution State defaults to Hidden.
- Solution State is Hidden, Visible, or Solved.
- Exact, case-sensitive `REMOVE` clears the text and hides the retained record.

The state column is ignored when Solution is blank or `REMOVE`.

## Hints column

Hints is blank or a JSON array:

```json
[
  {
    "title": "First clue",
    "content": "Look at the headers.",
    "cost": 10,
    "required_hints": []
  },
  {
    "title": "Second clue",
    "content": "Decode the token.",
    "cost": 20,
    "required_hints": [1]
  }
]
```

Required hint numbers are prior 1-based positions within that challenge's array.
An invalid requirement is removed with a warning while the hint remains.
Hint titles must be unique within the challenge.

## Validate and export

```bash
python3 tools/validate_challenges.py challenges.csv
python3 tools/validate_challenges.py challenges.csv \
  --output challenges.push.json
```

The decoded preview is always written to standard output. Blocking validation
errors return nonzero and prevent manifest output.
