# Workbook Authoring

Open `tools/push-challenges-template.xlsx` in Excel or another application that
preserves Excel data validation. The workbook has no macros, credentials, or
live connection to CTFd.

## Create a fresh workbook

The tools archive includes the ready-made template and the script that produces
it. To create another 500-row workbook:

```bash
python3 tools/create_workbook.py \
  --output event-challenges.xlsx
```

Use `--rows` when the authoring tables need a different capacity:

```bash
python3 tools/create_workbook.py \
  --output large-event.xlsx --rows 1000
```

The value must be at least `1`. It sets the available row count on each of the
Challenges, Flags, Solutions, and Hints sheets. The command replaces an
existing output file, so do not point it at a workbook containing authored
challenges unless that replacement is intentional.

## Challenges

Enter one challenge per row.

- `Name`: required, exact and case-sensitive.
- `Description`: Markdown challenge text; may be blank for a placeholder.
- `Value`: whole-number score. Zero and negative values are accepted.
- `Category`: required single category.
- `State`: Hidden, Visible, or Locked; defaults to Hidden.
- `Type`: Standard or Dynamic. Only Standard is currently supported.
- `Tags`: one or more hash-prefixed tags, such as
  `#beginner #web authentication`.
- `Next`: optional exact name of the next challenge. It may name another row or
  a challenge already in CTFd.
- `Logic`: Require Any Flag or Require All Flags.
- `Max Attempts`: nonnegative whole number; `0` means unlimited.
- `Attribution`: optional byline. Blank clears the value on overwrite.
- `Connection Info`: optional connection instructions. Blank clears the value
  on overwrite.

Every `#` starts a new tag. A tag continues until the next `#`, so
`#web authentication` is one tag containing a space. Text before the first
`#`, an empty tag, and duplicate tags are errors.

If a challenge has no flags, the validator stores Require Any Flag regardless
of the Logic cell and prints a normalization warning.

`Next` is case-sensitive. The workstation validator checks links among workbook
rows. The server dry-run also resolves existing CTFd challenges and checks the
complete projected hierarchy. Self-links and circular chains are prohibited.

## Flags

Enter one flag per row on the Flags sheet.

- `Challenge`: exact challenge name from the Challenges sheet.
- `Flag Type`: Static or Regex.
- `Content`: flag text or regular expression.
- `Matching`: Case Sensitive or Case Insensitive.

A challenge may have no flags or multiple flags. On overwrite, all existing
flags for that challenge are replaced by the rows in the workbook.

## Solutions

Enter at most one solution row per challenge.

- No row or blank `Content` preserves the existing solution.
- Text creates or overwrites the solution.
- `State` is Hidden, Visible, or Solved and defaults to Hidden.
- Exact, case-sensitive `REMOVE` clears existing solution text and forces
  Hidden state.

`REMOVE` does not delete the solution record or any attached files. It is a
no-op if no solution exists.

## Hints

Enter one hint per row on the Hints sheet.

- `Challenge`: exact input challenge name.
- `Title`: required and unique within that challenge.
- `Hint`: required hint text.
- `Cost`: nonnegative whole number; defaults to `0`.
- `Required Hints`: optional comma-separated, 1-based numbers of earlier hints
  for the same challenge.

Hint order is calculated separately per challenge in sheet order, even when
rows for different challenges are interleaved. If the third hint contains
`1,2`, both the first and second hints must be unlocked before it.

Excel does not validate Required Hints. If a value is malformed, duplicated,
zero, nonexistent, current, or forward, the validator imports the hint without
requirements and prints a warning. A hint whose Challenge no longer exists on
the Challenges sheet is omitted with a warning. Other malformed populated hint
rows block export.

On the server, an imported hint with the same exact title as an existing hint
is updated in place, preserving its ID and unlock history. Existing hints not
represented in the manifest remain untouched.

## Validate and export

Run:

```bash
python3 tools/validate_challenges.py challenges.xlsx
python3 tools/validate_challenges.py challenges.xlsx \
  --output challenges.push.json
```

Every run prints decoded scalar fields, tags, flags, solution intent, hints,
requirements, and hierarchy links. Review that output before transferring the
manifest. A blocking error produces a nonzero exit status and no manifest.
Nonblocking warnings are embedded in the manifest so the server dry-run shows
them again.

Files are intentionally outside this workflow. Add or remove challenge and
solution attachments manually in CTFd.
