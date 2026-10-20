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
Challenges, Flags, Solutions, Hints, and Bonus Tiers sheets. The command replaces an
existing output file, so do not point it at a workbook containing authored
challenges unless that replacement is intentional.

## Challenges

Enter one challenge per row.

- `Name`: required, exact and case-sensitive.
- `Description`: Markdown challenge text; may be blank for a placeholder.
- `Value`: whole-number fixed score for Standard, or initial score for Dynamic.
  Standard accepts zero and negative values; Dynamic requires zero or greater.
- `Category`: required single category.
- `State`: Hidden, Visible, or Locked; defaults to Hidden.
- `Type`: Standard or Dynamic.
- `Tags`: one or more hash-prefixed tags, such as
  `#beginner #web authentication`.
- `Next`: optional exact name of the next challenge. It may name another row or
  a challenge already in CTFd.
- `Logic`: Require Any Flag or Require All Flags.
- `Max Attempts`: nonnegative whole number; `0` means unlimited.
- `Attribution`: optional byline. Blank clears the value on overwrite.
- `Connection Info`: optional connection instructions. Blank clears the value
  on overwrite.
- `Scoring Function`: Linear or Logarithmic for Dynamic; blank for Standard.
- `Minimum Value`: nonnegative whole-number floor for Dynamic, no greater than
  Value; blank for Standard.
- `Decay`: positive whole number for Dynamic; blank for Standard. It uses the
  selected native CTFd scoring function's meaning, not a bonus percentage.
- `Bonus Mode`: blank preserves existing settings; Disabled stops future bonus
  awards; Absolute or Percentage replaces and enables the complete tier list.

For example, a Dynamic challenge can use Value `100`, Minimum Value `20`,
Decay `10`, and Scoring Function `Linear`. CTFd calculates its current value
using existing eligible solves when it is imported. Changing Dynamic settings
can therefore change existing players' live native scores; fixed bonus awards
and closed Monthly Game snapshots are not recalculated.

An existing challenge of a different type is **not converted**. The server
skips that entire challenge and lists it under `MANUAL ACTION REQUIRED` at the
end. Change its type manually in CTFd, then rerun. Other valid challenges still
import. Review the final callout even if the command succeeds.

When Excel stores a value entered in a text or content cell as a number, the
validator converts it to text before creating the manifest. For example, a
numeric flag value of `12345` becomes the string `"12345"`. Challenge values,
maximum attempts, and hint costs remain numeric. Excel discards leading zeros
from numeric cells, so format values such as `00123` as Text when those zeros
must be preserved.

Every `#` starts a new tag. A tag continues until the next `#`, so
`#web authentication` is one tag containing a space. Text before the first
`#`, an empty tag, and duplicate tags are errors.

If a challenge has no flags, the validator stores Require Any Flag regardless
of the Logic cell and prints a normalization warning.

`Next` is case-sensitive. The workstation validator checks links among workbook
rows. The server dry-run also resolves existing CTFd challenges and checks the
complete projected hierarchy. Self-links and circular chains are prohibited.

## Bonus Tiers

Bonus tiers are optional and require the updated Monthly Game plugin on the
server. They work with Standard or Dynamic challenges in individual mode.

Choose Absolute or Percentage in the challenge's Bonus Mode, then enter one
row per tier on Bonus Tiers:

- `Challenge`: select an exact authored challenge name.
- `Start Placement` and `End Placement`: inclusive positive whole numbers.
- `Amount`: nonnegative whole points for Absolute, or a nonnegative percentage
  for Percentage. Extra percentage decimals are truncated to two places.

Enter each challenge's tiers in placement order, starting at 1, with no gaps
or overlaps. For example, `1–1: 50`, `2–5: 25`, `6–10: 10` creates three tiers.
Zero amounts consume placements without awarding points. For Percentage,
the bonus uses the challenge value at solve time and truncates the resulting
points to a whole number. These are lifetime placements, not monthly ones.

Leave Bonus Tiers empty when Bonus Mode is blank or Disabled. Disabled keeps
existing tiers and placement progress; blank changes nothing. A tier for a
missing challenge, a gap or overlap, or tiers without an enabled mode blocks
export. Unlike orphan hints, orphan bonus rows are not silently discarded.

Imports do not revoke or recalculate existing bonus awards, reset placement
progress, or backfill awards for old solves. Enabling a new program counts
existing non-hidden solves as already consumed placements.

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

Older workbooks without the new scoring columns or Bonus Tiers sheet still
work for Standard challenges and preserve bonus settings. New exports use
manifest version 2; update the server plugin before importing them. Existing
version-1 manifests remain accepted.

Files are intentionally outside this workflow. Add or remove challenge and
solution attachments manually in CTFd.
