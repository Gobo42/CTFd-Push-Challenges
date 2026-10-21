# Scoring and first-solver bonuses

This guide is for challenge authors choosing points in the Push Challenges
workbook. You don't need a scoring background. It explains fixed and Dynamic
base scores, the Scoring Function/Minimum Value/Decay fields, and separate
first-solver bonus tiers through worked examples. For every worksheet field
and entry instructions, see [Workbook authoring](workbook-authoring.md).

## Two separate kinds of points

A challenge can contribute points in two different ways:

- **Base score:** the challenge's ordinary points for solving it. Standard
  challenges have a fixed value; Dynamic challenges have a shared value that
  decreases as more accounts solve them.
- **First-solver bonus:** extra points awarded to a limited number of early
  solvers. Monthly Game records these as separate CTFd Awards. Bonuses can be
  added to Standard or Dynamic challenges.

For example, a 200-point Standard challenge with a 50-point first-solver bonus
gives the first solver 200 base points plus a separate 50-point award. Later
solvers still receive 200 base points, even after the bonus places run out.

You don't have to use either advanced feature. Type `Standard`, Value `100`,
blank Dynamic settings, blank Bonus Mode, and no Bonus Tiers rows is a valid
fixed-score configuration. Blank Bonus Mode preserves any bonus configuration
already on the server; it doesn't switch an existing program off.

## Standard scores

Use Standard when you want a predictable base value regardless of the number
of solvers. Enter the whole-number points in Value and leave Scoring Function,
Minimum Value, and Decay blank. For example, Value `200` gives the challenge a
200-point base value for its first, fifth, and hundredth solvers.

Zero is allowed, including for placeholders. Negative Standard values are also
accepted, but reduce the account's score when solved; use them only if that is
your intended design. Adding multiple flags doesn't multiply the base score.

## Dynamic scores

Use Dynamic when a widely solved challenge should become worth less than a
rarely solved challenge. Its point value changes with successful solves, not
with time, failed submissions, or how often the challenge is opened.

The value is shared, not locked separately for each solver. If Alice solves
when the challenge is worth 500 points and later solves reduce it to 300,
its contribution to Alice's live native CTFd total is also 300. This is
different from first-solver bonus Awards, which stay fixed after creation.
Closed Monthly Game snapshots also stay fixed.

In individual mode, eligible accounts are players. In team mode, they are
teams. CTFd's native decay count excludes hidden and banned accounts. Multiple
required flags complete one challenge solve; they don't each advance its
Dynamic solve count.

The examples here follow the native CTFd implementation used by Push
Challenges. It keeps the initial value through the first eligible solve, so
the second eligible solver is the first one that can lower the shared score.
Rounding can leave adjacent solve counts at the same value.

### Dynamic fields

Set Type to `Dynamic` and fill in all four scoring fields:

| Field | Meaning | Example |
| --- | --- | --- |
| Value | Initial base score, before decay; a nonnegative whole number. | `500` |
| Scoring Function | The rule that turns the solve count into the shared base value: Linear or Logarithmic. | `Linear` |
| Minimum Value | Floor below which the base value cannot fall; a nonnegative whole number no greater than Value. | `100` |
| Decay | A positive whole number whose meaning depends on the selected function. It isn't a percentage or a number of days. | Linear `40` or Logarithmic `10`, as explained next. |

Value and Minimum Value can be equal, in which case the base value stays
constant. Changing these settings on an existing Dynamic challenge
recalculates its shared value using existing eligible solves. Importing it
again doesn't reset its solve count.

## Linear scoring

Linear subtracts the same number of points for each eligible solve after the
first. **Decay is the number of points to subtract**, until Minimum Value is
reached.

For Value `500`, Minimum Value `100`, and Decay `40`, the first solver leaves
the value at 500. The second reduces it to 460, the third to 420, and the
eleventh reaches the 100-point floor. Further solves don't lower it below 100.

A larger Linear Decay makes points fall faster: `80` subtracts twice as many
points per additional solver as `40`. To plan a floor after ten additional
solvers, divide the 400-point difference between 500 and 100 by ten:
`400 / 10 = 40`.

For readers who want the formula, let `n` be the eligible solve count beyond
the first, or zero before anyone solves. CTFd calculates:

```text
value = max(Minimum Value, Value - Decay * n)
```

## Logarithmic scoring

Logarithmic starts with small reductions and makes the reductions larger as
the solve count grows. **Decay is the number of additional eligible solves
after the first needed to reach Minimum Value.** It is not points subtracted
per solver.

For Value `500`, Minimum Value `100`, and Decay `10`, the first solver leaves
the value at 500. The second reduces it to 496, the third to 484, and the
eleventh reaches 100. Further solves leave it at the floor.

A larger Logarithmic Decay makes points fall more slowly: changing it from
`10` to `20` moves the floor from the eleventh to the twenty-first eligible
solve. This is the opposite of increasing Linear Decay. Don't copy a Decay
number between functions and expect the same behavior.

Although the CTFd option is named Logarithmic, the implementation used here
uses a squared solve-count curve, not a mathematical logarithm. With `n`
defined as in the Linear example, CTFd calculates:

```text
raw value = Value - (Value - Minimum Value) * (n / Decay)^2
value = max(Minimum Value, round raw value up to a whole point)
```

Rounding is **up**, not to the nearest whole number. For example, with Value
`100`, Minimum Value `20`, and Decay `10`, the second solve produces 99.2 and
therefore displays 100; the third produces 96.8 and displays 97.

## Compare the two functions

These configurations both start at 500 and reach 100 on the eleventh eligible
solve. Their Decay values differ because the functions interpret Decay
differently: Linear uses `40`; Logarithmic uses `10`.

The table shows the shared base value after the stated number of eligible
solves, not a list of fixed awards to individual players:

| Eligible solves | Linear: Decay 40 | Logarithmic: Decay 10 |
| --- | --- | --- |
| 0 | 500 | 500 |
| 1 | 500 | 500 |
| 2 | 460 | 496 |
| 3 | 420 | 484 |
| 6 | 300 | 400 |
| 11 | 100 | 100 |
| 12 | 100 | 100 |

Choose Linear for a constant point reduction. Choose Logarithmic when you
want to keep more points for the earliest solves and reduce them more steeply
later. Preview your intended solve counts before deploying a scoring curve.

## First-solver bonuses

Bonuses reward early solves without changing the base scoring rule. They
require a compatible Monthly Game plugin and individual-player mode. A
placement means the order in which a player solves that challenge, not their
overall leaderboard rank or a flag's position in the workbook.

Bonus placements cover the challenge's lifetime. Monthly rollover does not
renew them. A challenge with several required flags gets a placement when
the challenge is fully solved, not when its first partial flag is submitted.

### Bonus modes

Choose one mode on the challenge's Challenges row:

| Bonus Mode | Meaning | What to put on Bonus Tiers |
| --- | --- | --- |
| Leave blank | Preserve all existing bonus settings. No program is created for a challenge without one. | No rows for this challenge. |
| Disabled | Stop future bonus awards without deleting saved tiers, issued awards, or placement progress. | No rows for this challenge. |
| Absolute | Enable bonuses using fixed whole-number points per eligible solver. Replace the full configured tier list. | At least one complete contiguous tier list. |
| Percentage | Enable bonuses using a percentage of the captured base value at solve time. Replace the full configured tier list. | At least one complete contiguous tier list. |

Absolute and Percentage are alternatives for the entire challenge; you cannot
make one tier Absolute and another Percentage. Each range is one **tier**,
even when it includes several placements. The amount applies to each solver
in that range, not a shared pool divided among them.

### Absolute example

Suppose Header Hunt is a 200-point Standard challenge with Bonus Mode
`Absolute`. Its Bonus Tiers rows can be:

| Challenge | Start Placement | End Placement | Amount |
| --- | --- | --- | --- |
| Header Hunt | 1 | 1 | 50 |
| Header Hunt | 2 | 5 | 25 |
| Header Hunt | 6 | 10 | 10 |

These rows mean:

- The first solver gets 200 base points plus a 50-point bonus: 250 total.
- Solvers 2, 3, 4, and 5 each get 200 plus 25: 225 each.
- Solvers 6 through 10 each get 200 plus 10: 210 each.
- Solver 11 and every later solver get only the 200 base points.

The first award is named `First to solve Header Hunt`. The second tier uses
`Tied for second to solve Header Hunt`; the third uses
`Tied for sixth to solve Header Hunt`. Here, “tied” means the configured range
receives the same bonus, not that the solves happened simultaneously. Trophy
numbers follow tier order: the whole 2–5 range uses trophy 2, and the whole
6–10 range uses trophy 3. Later tiers use a generic trophy.

### Percentage example

With Bonus Mode `Percentage`, an Amount of `20` means 20%, not 20 points.
For a captured base value of 500, it gives a separate 100-point award:
`500 * 20 / 100 = 100`.

Percentage amounts truncate to two decimal places, and the resulting bonus
truncates to whole points. For an entered Amount of `12.999` and a captured
base value of 333, the calculation is:

```text
saved percentage = 12.99
bonus = 333 * 12.99 / 100 = 43.2567
award = 43 points
```

Enter `12.999` as an ordinary number. Don't type a `%` sign or format the cell
as Percentage: Excel stores `12.5%` as `0.125`. That becomes a 0.12% bonus
after truncation, not 12.5%. Use an ordinary cell containing `12.5` for 12.5%.

For Dynamic challenges, the percentage uses the value available when the solve
is recorded, before CTFd's post-solve decay recalculation. A later scoreboard
value can therefore differ from the value used to calculate that award.
After creation, the award stays fixed even if the base value or bonus settings
change. A calculation that truncates to zero creates no points award.

### Range rules and zero amounts

List each challenge's tiers in ascending order, starting at placement 1.
End Placement includes that position. Every following Start Placement must be
one more than the previous End Placement:

- Valid: `1–1`, `2–5`, `6–10`.
- Invalid: `1–1`, `3–5`, because placement 2 is missing.
- Invalid: `1–3`, `3–5`, because placement 3 appears twice.
- Valid: `1–1` with Amount `50`, followed by `2–5` with Amount `0`.

Zero tiers consume those placements without awarding points. You don't need
an extra zero tier after your last rewarded placement; later solvers
automatically get no bonus. Negative amounts are prohibited. Absolute amounts
must be whole numbers; percentages can have decimals.

### Existing challenges and later edits

Turning bonuses on doesn't reward earlier solves retroactively. A new program
counts existing non-hidden solves as already consumed placements. If five
players already solved Header Hunt, its next placement starts at 6, not 1.

Changing tiers, disabling/re-enabling bonuses, deleting a solve, or revoking an
award doesn't reset or reuse consumed placements. Non-hidden solves continue
to consume placements while a saved program is disabled. If you enable a
program again, its saved tiers apply to the next lifetime placement.

An administrator can revoke a bonus Award. Revocation reduces the live
all-time total and, when applicable, the open monthly total. It doesn't promote
another solver or rewrite a closed monthly snapshot.

## Common mistakes

Before sending your workbook, check these cases:

- **“Dynamic means a monthly reset.”** It doesn't. Decay follows eligible
  solves across the challenge's lifetime, not the calendar.
- **“Minimum Value is a bonus threshold.”** It is only the floor for base
  points. It doesn't control who gets a bonus.
- **“Decay 10 means 10%.”** Neither native function interprets it that way.
- **“All solvers keep their original Dynamic base points.”** The native base
  contribution changes for earlier solvers too; separate bonus awards stay fixed.
- **“2–5 means tier numbers 2 and 5.”** It means four solver placements in one
  tier: second, third, fourth, and fifth.
- **“Blank Bonus Mode removes old bonuses.”** It preserves them. Use Disabled
  to stop future bonus awards.
- **“Deleting one bonus row leaves the old tier on the server.”** With an
  enabled mode, import replaces the entire tier list; enter the full intended list.
- **“Deleting a workbook challenge deletes it from CTFd.”** It doesn't. This
  tool creates or overwrites challenges; it never deletes them.

## What's next

See [Workbook authoring](workbook-authoring.md#challenges) to enter your chosen
settings, and use the validator to review their decoded values. Have an event
administrator review the intended scoring curve and bonus places before import.
The server's dry-run checks existing types and references but does not simulate
a series of future solves or awards. See the
[operator guide](operator-guide.md) for safe dry-run and apply procedures.
