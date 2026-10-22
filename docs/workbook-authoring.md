# Workbook authoring

This guide is for challenge authors filling in the Excel workbook, including
authors who don't administer CTFd. It explains every input field and how your
choices affect imports. For points, decay, and first-solver rewards, see the
[scoring and bonus guide](scoring-guide.md). Server setup belongs in the
[installation guide](installation.md).

## Before you begin

Open `tools/push-challenges-template.xlsx` in Excel or another application that
preserves Excel data validation. Save your working copy under a different
name, such as `event-challenges.xlsx`. The workbook has no macros, credentials,
or live connection to CTFd. Saving it doesn't publish challenges.

Ask your administrator whether to use fixed or Dynamic scores and whether the
server supports Monthly Game bonus imports. Bonuses require a compatible
Monthly Game plugin and individual-player mode. Standard or Dynamic challenges
without bonus changes don't require Monthly Game.

## Choose the sheet for your task

Challenge names connect the sheets:

| Sheet | What you put there |
| --- | --- |
| Instructions | Nothing to fill in; read the workflow summary. |
| Challenges | One row per challenge, including its instructions and scoring choices. |
| Flags | One row per accepted answer or answer pattern; several rows can belong to one challenge. |
| Solutions | At most one walkthrough per challenge, with its visibility setting. |
| Hints | One row per clue, with a point cost and any earlier required hints. |
| Bonus Tiers | One row per range of rewarded solver placements, such as first place or places 2–5. |
| Lists | Nothing to fill in; this hidden sheet supplies dropdown choices. |

Enter challenge names first, then select them on related sheets. Names are
case-sensitive: `Header Hunt` and `header hunt` are different. Don't rename
headers or delete required sheets. Leave unused rows empty apart from the
template's prefilled defaults.
Keep challenge-name rows together without empty gaps so the related-sheet
dropdowns include the full list. Those dropdowns list workbook names, not
every challenge already on the CTFd server.

## Create your first challenge

For a fixed-score challenge with one answer:

1. On **Challenges**, enter `Header Hunt` in **Name**.
2. Enter `Find the flag in the HTTP response headers.` in **Description**.
3. Enter `100` in **Value** and `Web` in **Category**.
4. Keep **State** as `Hidden`, **Type** as `Standard`, **Logic** as
   `Require Any Flag`, and **Max Attempts** as `0`.
5. Leave the three Dynamic settings and **Bonus Mode** blank.
6. On **Flags**, select `Header Hunt` in **Challenge**, `Static` in
   **Flag Type**, enter `flag{header_hunt}` in **Content**, and select
   `Case Sensitive` in **Matching**.
7. Save the workbook and follow [Validate and export](#validate-and-export),
   or ask your operator to run validation for you.

Confirm that the preview shows a Hidden, Standard challenge worth 100 points
and the expected flag. After import, an administrator can review it before
making it Visible.

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

- `Name`: required unique name, up to 80 characters, exact and case-sensitive.
  An existing exact name selects an overwrite. Changing a name creates a
  different challenge; it doesn't rename the old one.
- `Description`: the instructions players read, with Markdown formatting;
  up to 65,535 characters. Blank is allowed for a placeholder and clears an
  existing description on overwrite.
- `Value`: required whole-number fixed score for Standard, or initial score for Dynamic.
  Standard accepts zero and negative values; Dynamic requires zero or greater.
- `Category`: required single category, up to 80 characters, such as `Web`.
  This groups challenges; Tags supplies multiple labels instead.
- `State`: Hidden, Visible, or Locked; defaults to Hidden, including when blank.
  Visible permits normal player access subject to CTFd's other restrictions.
  Hidden and Locked keep the challenge out of normal player listings; Locked
  explicitly refuses submissions. Neither schedules an automatic unlock.
- `Type`: Standard for fixed points, or Dynamic for a shared point value that
  decreases as more accounts solve the challenge. Keep the template's Standard
  default unless you intend to supply Dynamic settings; don't leave it blank.
- `Tags`: optional hash-prefixed labels, such as
  `#beginner #web authentication`.
- `Next`: optional exact name of the next challenge. It may name another row or
  a challenge already in CTFd. Blank clears an existing Next link. This is a
  navigation link, not a challenge prerequisite or automatic unlock rule.
- `Logic`: Require Any Flag accepts one matching configured flag. Require All
  Flags requires the account to submit all configured flags before the
  challenge is solved. Default/blank is Any.
- `Max Attempts`: required nonnegative whole number; keep the default `0` for
  unlimited attempts. `5` limits incorrect attempts according to the site's
  CTFd lockout/timeout policy; ask your administrator which policy applies.
- `Attribution`: optional credit or byline, such as `Written by Example Team`.
  Blank clears the value on overwrite.
- `Connection Info`: optional connection instructions, such as
  `nc challenge.example.org 31337`. Blank clears the value on overwrite.
- `Scoring Function`: required Linear or Logarithmic for Dynamic; blank for Standard.
- `Minimum Value`: required nonnegative whole-number floor for Dynamic, no greater than
  Value; blank for Standard. This is the lowest base score, not a minimum
  player score or a bonus threshold.
- `Decay`: required positive whole number for Dynamic; blank for Standard. It uses the
  selected native CTFd scoring function's meaning, not a bonus percentage.
- `Bonus Mode`: blank preserves existing settings; Disabled stops future bonus
  awards; Absolute or Percentage replaces and enables the complete tier list.
- `Position`: optional nonnegative whole number, up to `2147483647`.
  Positive positions sort lowest first, before automatic-position challenges.
  Blank preserves an existing position or leaves a new challenge at `0`.
  Explicit `0` restores CTFd's automatic ordering by point value.

For the meaning of each scoring setting and numerical examples, see
[Dynamic fields](scoring-guide.md#dynamic-fields) and
[bonus modes](scoring-guide.md#bonus-modes). A Standard challenge with bonus
tiers still has Type Standard and leaves all three Dynamic settings blank.

For example, a Dynamic challenge can use Value `100`, Minimum Value `20`,
Decay `10`, and Scoring Function `Linear`. CTFd calculates its current value
using existing eligible solves when it is imported. Changing Dynamic settings
can therefore change existing players' live native scores; fixed bonus awards
and closed Monthly Game snapshots are not recalculated.

An existing Standard/Dynamic type mismatch is **not converted**. The server
skips that entire challenge and lists it under `MANUAL ACTION REQUIRED` at the
end. Change its type manually in CTFd, then rerun. Other valid challenges still
import. Review the final callout even if the command succeeds.
Unsupported third-party challenge types are blocking errors rather than skips.

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
of the Logic cell. If it changes All to Any, it prints a normalization warning.

`Next` is case-sensitive. The workstation validator checks links among workbook
rows. The server dry-run also resolves existing CTFd challenges and checks the
complete projected hierarchy. Self-links and circular chains are prohibited.

### Set challenge display order

Set Position to keep a series together within a category even when its point
values differ. For example, use these positions for seven challenges in the
same category:

| Name | Position |
| --- | --- |
| Challenge A 1/4 | 10 |
| Challenge A 2/4 | 20 |
| Challenge A 3/4 | 30 |
| Challenge A 4/4 | 40 |
| Challenge B 1/3 | 50 |
| Challenge B 2/3 | 60 |
| Challenge B 3/3 | 70 |

Leaving gaps lets you insert another challenge later, such as Position `15`.
Use distinct positions within each category: equal positions fall back to
point value, then database ID. Challenges at Position `0` appear after all
positive positions, ordered by point value and then ID.

Workbook row order, challenge names, and Next links don't assign positions.
Position works for Standard and Dynamic challenges. Categories still group
challenges, and a custom theme's sorting rules can override native ordering.
After import, confirm the player-facing challenge list follows the intended
sequence.

Administrators can also enable **Group by category and position** on CTFd's
admin challenge list. That optional browser preference reuses these same
Position values within each category. It does not require unique positions
across categories. See [Admin list ordering](operator-guide.md#admin-list-ordering).

## Bonus Tiers

Bonus tiers are optional and require a compatible Monthly Game plugin on the
server. They work with Standard or Dynamic challenges in individual mode.

Choose Absolute or Percentage in the challenge's Bonus Mode, then enter one
row per tier on Bonus Tiers:

- `Challenge`: select an exact authored challenge name. It must exist on
  Challenges; an unknown reference blocks export rather than being ignored.
- `Start Placement`: positive whole number for the first solver position in
  this tier. The first tier must start at 1.
- `End Placement`: positive whole number for the last included position,
  at least Start Placement. A range from 2 to 5 includes solvers 2, 3, 4, and 5.
- `Amount`: nonnegative whole points for Absolute, or a nonnegative percentage
  for Percentage. Extra percentage decimals are truncated to two places.
  The amount applies to each solver in the range, not a shared pool.
  Enter percentages as ordinary numbers: `12.5` means 12.5%.

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

For complete tier examples, award names, trophy numbering, and the interaction
with Dynamic values, see [First-solver bonuses](scoring-guide.md#first-solver-bonuses).

## Flags

Enter one flag per row on the Flags sheet.

- `Challenge`: required exact challenge name from Challenges. Unknown references
  block export.
- `Flag Type`: required Static for literal answer text or Regex for a
  regular-expression pattern. Use Static unless you need a pattern.
- `Content`: required flag text or pattern. For example, Static
  `flag{header_hunt}` accepts that answer. Regex `flag\{[0-9]+\}` accepts
  `flag{123}` but not `flag{abc}`.
- `Matching`: required Case Sensitive or Case Insensitive. Sensitive
  distinguishes `Flag` from `flag`; Insensitive accepts either capitalization.

A regex must match the submitted answer in full. Enter the pattern directly
in the cell, without `/` delimiters or JSON escaping. An administrator should
review patterns; workbook validation doesn't prove a regex is correct or safe.

For two alternative answers, add two rows and choose Require Any Flag. For two
required answers, add distinct rows and choose Require All Flags; players
submit them separately. Completing the challenge gives its base score once,
not once per flag. Avoid overlapping patterns if you intend distinct answers.

A challenge may have no flags or multiple flags. On overwrite, all existing
flags for that challenge are replaced by the rows in the workbook.
Removing all its flag rows removes its flags on overwrite. Flagless
placeholders aren't automatically solved. Exact duplicate flag definitions
are errors.

## Solutions

Enter at most one solution row per challenge.

- `Challenge`: required exact name from Challenges. Unknown references and
  duplicate solution rows block export.
- `Content`: walkthrough text explaining how to solve the challenge, not an
  accepted flag. For example, `Inspect response headers with browser tools.`
  No row or blank content preserves the existing solution. Text creates or
  overwrites it; exact `REMOVE` requests the clear behavior described here.
- `State`: Hidden, Visible, or Solved; defaults to Hidden.
  Hidden doesn't expose the walkthrough to ordinary players. Visible exposes
  it to eligible players; Solved exposes it after their account solves the
  challenge. Blank means Hidden when Content contains text.

Exact, case-sensitive `REMOVE` clears existing solution text and forces Hidden
state without deleting the record or any attached files. It is a no-op if no
solution exists. State is ignored when Content is blank or `REMOVE`.

## Hints

Enter one hint per row on the Hints sheet.

- `Challenge`: required exact input challenge name. Unknown references are
  ignored with a warning, as described here.
- `Title`: required and unique within that challenge, up to 80 characters.
  For example, `Inspect the response`. Exact-title matches update existing hints.
- `Hint`: required clue text, such as `Look at headers, not only the page body.`
- `Cost`: required nonnegative whole number; keep the default `0` for a free
  clue. A cost of `10` deducts 10 points when the account unlocks the hint.
- `Required Hints`: optional comma-separated, 1-based numbers of earlier hints
  for the same challenge.

These are hint positions, not Excel row numbers or database IDs. For example,
three hints for Header Hunt can use the following entries:

| Hint number | Title | Hint | Cost | Required Hints |
| --- | --- | --- | --- | --- |
| 1 | Start here | Inspect the response. | 0 | Leave blank |
| 2 | Narrow it down | Look for an unusual header. | 5 | `1` |
| 3 | Final clue | Decode the header value. | 10 | `1,2` |

The third hint requires both earlier hints, not any two hints. Unlocking all
three costs 15 points in total. Each challenge has its own hint numbering;
reordering rows can change what the prerequisite numbers refer to.

Excel does not validate Required Hints. If a value is malformed, duplicated,
zero, nonexistent, current, or forward, the validator imports the hint without
requirements and prints a warning. A hint whose Challenge no longer exists on
the Challenges sheet is omitted with a warning. Other malformed populated hint
rows block export.
Dropping a requirement removes the entire list for that hint and can make it
accessible earlier than intended, so review every warning.

On the server, an imported hint with the same exact title as an existing hint
is updated in place, preserving its ID and unlock history. Existing hints not
represented in the manifest remain untouched.
Deleting a hint row from the workbook doesn't delete that hint from CTFd.

## Excel entry rules

Use literal values, not formulas, in authored cells. The validator reads formula
text; it doesn't calculate Excel formulas. If you used formulas to prepare
content, copy the results and use Excel's **Paste Special → Values** in your
authoring copy before validation.

Excel can discard leading zeros or round long numbers before the validator
sees them. Format identifiers, long flags, and values such as `00123` as Text
before entering them. Lost digits can't be reconstructed.

Don't format bonus amounts as Excel percentages. Excel stores `12.5%` as
`0.125`, which becomes a 0.12% bonus after truncation, not 12.5%. Use an
ordinary numeric cell containing `12.5`. Line breaks and Markdown in content
cells don't need JSON formatting.

## Validate and export

If another person runs the tools for you, send the saved `.xlsx` file and ask
them for the decoded preview and warnings. If you run them yourself, first
follow the [authoring-tools setup](installation.md#authoring-tools).

From the tools directory, validate and optionally export:

```bash
python3 tools/validate_challenges.py event-challenges.xlsx
python3 tools/validate_challenges.py event-challenges.xlsx \
  --output challenges.push.json
```

`event-challenges.xlsx` is your saved workbook. `challenges.push.json` is the
exported file for the server operator.

Every run prints decoded scalar fields, tags, flags, solution intent, hints,
requirements, and hierarchy links. Review that output before transferring the
manifest. A blocking error produces a nonzero exit status and no manifest.
Nonblocking warnings are embedded in the manifest so the server dry-run shows
them again.

The input file must be readable. Saving edits requires write access to the
workbook; generating a workbook or exporting JSON requires write access to the
chosen output directory and any existing output file. These are workstation
paths, not writable directories inside the deployed plugin.

If validation fails, don't send an older output file as if it were a fresh
export. Keep workbooks and manifests private: they can contain unreleased
challenge answers.

Older workbooks without the scoring columns or Bonus Tiers sheet still work
for Standard challenges and preserve bonus settings. The tools export manifest
version 2; update the server plugin before importing it. Existing
version-1 manifests remain accepted.
Workbooks with the scoring columns but without Position also remain accepted;
they preserve existing positions. Update both the tools and server plugin to
use Position.

Files are intentionally outside this workflow. Add or remove challenge and
solution attachments manually in CTFd.

## Review overwrite behavior

Before importing into a populated event, remember:

- Managed fields, including descriptions and blank attribution/connection
  information, are set to the workbook values.
- Flags and tags are replaced completely; blank lists remove existing ones.
- Blank solution content preserves a solution; `REMOVE` clears and hides it.
- Omitted hints are preserved; exact-title hints update in place.
- Blank Bonus Mode preserves bonuses; an enabled mode replaces all tiers.
- Blank Position preserves the existing position; explicit `0` resets it to
  automatic point ordering.
- Challenges, files, solves, submissions, and attempt history are not deleted.

Confirm that the preview matches the intended flags, costs, visibility, score
curve, and bonus ranges. Ask your operator to follow the
[dry-run and apply workflow](operator-guide.md). A successful partial import
can still list skipped challenges under `MANUAL ACTION REQUIRED`; review that
final section too.
