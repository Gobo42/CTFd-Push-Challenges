# Operator Guide

## Workflow

Stage the validated manifest where the `ctfd` service account can read it, as
described in [Installation](installation.md#filesystem-permissions). Record its
digest, then run the default dry-run through the established `ctfd-cli`
launcher:

```bash
sha256sum /srv/ctfd-imports/challenges.push.json
ctfd-cli push-challenges import /srv/ctfd-imports/challenges.push.json
```

Dry-run validates the manifest, compares exact challenge names, resolves all
`Next` links, checks the complete projected hierarchy, matches hints, and
prints every planned action. It exits without writing.

Review:

- CREATE versus OVERWRITE classification;
- scalar fields and blank values that will clear data;
- flag and tag replacement counts;
- solution preserve, upsert, or clear intent;
- hint create, update, preserve, and requirement resolution;
- `Next` targets;
- Position values, including explicit `0` versus preserve/default;
- retained authoring warnings;
- Dynamic initial/minimum/decay/function settings and bonus preserve, disable,
  or replace intent;
- the final skip count and `MANUAL ACTION REQUIRED` section.

The launcher propagates the importer's exit status. A nonzero result means the
dry-run failed; correct the reported problem and repeat it. Do not apply a
manifest whose dry-run failed.

After review, confirm that the digest has not changed and apply the exact same
manifest by adding `--apply`:

```bash
sha256sum /srv/ctfd-imports/challenges.push.json
ctfd-cli push-challenges import \
  /srv/ctfd-imports/challenges.push.json --apply
```

The two digest outputs must match. If they differ, stop and dry-run the changed
file before applying it. The importer is non-interactive and can be logged or
redirected; the example launcher allocates a terminal for the transient
systemd unit and prints its unit name and invocation ID.

An apply success returns zero, including a successful subset with skips.
Verify the affected challenges in CTFd after
the command completes. A nonzero result means the transaction did not complete
unless the output explicitly identifies a post-commit cache warning. See
[Troubleshooting](troubleshooting.md).

## Matching and replacement rules

Challenge names and references are exact and case-sensitive. A matching
Standard or Dynamic challenge of the requested type is overwritten. No match
creates that type. Multiple exact database matches are an error and include
the conflicting IDs. Unsupported scoring functions are errors.
Existing third-party challenge types are unsupported and also abort preflight.

An existing type mismatch skips **only that challenge**, including all its
scalar fields, flags, tags, hints, solution, Next link, and bonus configuration.
Other valid challenges still import atomically. References to a skipped
challenge resolve to its unchanged existing record, and cycle checks retain
its existing outgoing Next link.

After the detailed list and dry-run/apply/cache messages, the command prints
create, overwrite, and skip counts. Any skips produce a final
`MANUAL ACTION REQUIRED` section naming the challenge and existing/requested
types. Change those types manually in CTFd and rerun. Do not infer that every
challenge imported from a zero exit status.

## Dynamic scoring and bonus configuration

Give authors the [workbook field guide](workbook-authoring.md) and
[scoring and bonus examples](scoring-guide.md) before collecting their input.

Dynamic imports require CTFd's native `dynamic_challenges` plugin. They set
initial value, minimum, decay, and Linear/Logarithmic function, then recalculate
the current value from existing eligible solves using CTFd's own function.
This can change live native cumulative scores. It does not rewrite solves,
fixed bonus awards, or closed Monthly Game snapshots.

Bonus Mode defaults to preserve. Disabled stops future bonuses while retaining
the saved tiers and lifetime progress. Absolute/Percentage enable and replace
the complete tier configuration without resetting progress or changing issued
awards. New programs count existing non-hidden solves without granting
retroactive bonuses. See [Bonus Tiers](workbook-authoring.md#bonus-tiers).

Non-preserve bonus actions require a compatible, loaded Monthly Game plugin;
otherwise the entire import fails preflight without writes. Skipped challenges
do not trigger this dependency check. Standard/Dynamic imports that preserve
bonuses do not require Monthly Game. Deploy both updated server plugins when
using bonus configuration; new authoring exports use version-2 manifests.
The server also accepts legacy version-1 Standard manifests.

## Managed fields

Imported scalar fields, Logic, Max Attempts, Attribution, and Connection Info
are set to manifest values. Blank Attribution and Connection Info therefore
clear existing values.

Flags and tags are completely replaced for every imported challenge. Empty
arrays remove all existing flags or tags. Flagless challenges always use Any
logic.

Solution behavior is explicit:

- preserve leaves an existing solution untouched;
- upsert creates or updates it in place;
- clear empties and hides an existing record without deleting it.

Imported exact-title hint matches are updated in place. Unmatched titles create
hints. Existing omitted hints are preserved. Imported requirements replace
requirements for those imported hints.

`next: null` clears a challenge's current `next_id`. A name resolves against
the input and existing CTFd challenges. Unknown targets, ambiguity, self-links,
and circular chains abort preflight.

Position is optional in version-2 manifests. A missing or null `position`
preserves an overwrite target's position; a new challenge keeps default `0`.
An integer from `0` through `2147483647` sets the native CTFd field. Positive
positions sort lowest first; `0` places a challenge after positioned challenges
and orders it by points. Equal positions fall back to points, then database ID.
Row order and Next links do not assign positions. Custom themes can override
native ordering, so verify the player-facing list after applying. See
[Set challenge display order](workbook-authoring.md#set-challenge-display-order).
Update both the tools and server plugin before importing Position exports.

## Preserved data

The importer never deletes:

- challenges;
- hints;
- solution records;
- challenge or solution file records;
- stored files.

It does not modify attachments, solves, submissions, attempts, challenge
requirements, module membership, or fields outside the supported manifest.
Position is preserved unless explicitly supplied. Hint updates preserve hint IDs
and unlock/payment history. Solution
updates preserve the solution ID and attachment links.

## Admin list ordering

Open CTFd's existing **Challenges** admin list. Push Challenges adds a
**Group by category and position** checkbox above the table. It is unchecked
by default and does not change CTFd's normal row order until enabled.

When checked, the visible rows sort by Category, then Position within that
category. Position `0` comes last in each category; equal positions fall back
to current point value, then ID. For example, Crypto positions `10,20,30` and
Web positions `10,20,30,40,50` remain separate groups. A fifth Web challenge
can appear after its fourth even when its database ID is much higher.

The browser remembers the checked or unchecked state in `localStorage`, scoped
to the site's origin and CTFd installation path. It is not a global CTFd
setting or an account preference. Another browser starts unchecked; admins
sharing a browser profile share its choice. Clearing browser storage resets
it. Private browsing might not retain it after the private session closes.

Unchecking restores the row order originally supplied by CTFd. Toggling moves
existing rows without reloading, so selected challenge checkboxes, filters,
and links remain intact. Existing column-header sorting still works; the
remembered grouping is reapplied on the next page load if enabled. If browser
storage is blocked, the control still works for the current page and displays
a message that the choice cannot be remembered.

This affects only the existing admin list. It does not change IDs, saved
positions, scores, player-facing ordering, or CLI list order. No server-side
preference or writable directory is added, and CTFd's source and templates
remain unchanged. The control expects CTFd's standard admin challenge-table
markup; a custom admin interface might require compatibility work.

## Transactions and failures

All imported challenge, Dynamic scoring, bonus configuration, flag, tag, solution, hint,
requirement, and hierarchy changes in the eligible subset
use one ORM transaction and one commit. Any failure before commit rolls back
the complete import and returns nonzero. Add `--debug` only when an unexpected
exception traceback is needed.

After commit, the command clears CTFd challenge and standings caches. A cache
failure is printed as a post-commit warning. That warning means the database
transaction succeeded; it must not be interpreted as a rollback.

## Delete challenges

Use these separate maintenance commands when replacing old challenges, not
the workbook or import manifest. Imports remain add/overwrite-only.

**Warning:** Deletion permanently removes challenges and their associated
solves, incorrect submissions, flags, tags, hints, solutions, and attached
files using the same registered challenge-type handlers as the CTFd web UI.
Back up both the CTFd database and upload storage before proceeding.

1. List the actual database IDs and review names, categories, types, points,
   and visibility states:

   ```bash
   ctfd-cli push-challenges list
   ```

2. Start interactive selection:

   ```bash
   ctfd-cli push-challenges delete
   ```

   The command lists challenges and prompts for IDs. Enter a comma-separated
   selection such as `47,49,55-58`. Ranges are inclusive. Spaces and repeated
   IDs are allowed; each selected ID is attempted once, in ascending order.
   Every ID in a range must exist. Malformed selections, reversed ranges,
   nonexistent IDs, or unavailable selected challenge types abort before any
   deletion.

3. Review the selected challenges and warning. Type exact lowercase `yes` to
   proceed. Any other answer or an end-of-input before confirmation deletes
   nothing. There is no `--yes` bypass or automatic retry.

4. Review every result and the final summary. Each success prints `DELETED:`;
   each failure prints `FAILED:` with its ID, name, and reason. Failures are
   repeated under `MANUAL ACTION REQUIRED` at the end. Run the list command
   again to verify the remaining challenges before retrying failed IDs.

If you already know the IDs, supply the selection directly and still review
and confirm the preview:

```bash
ctfd-cli push-challenges delete '47,49,55-58'
```

Deletion runs **sequentially**, not as overlapping web requests. CTFd commits
each challenge separately; file cleanup can also commit during one deletion.
This is not an atomic batch. A later failure, interruption, or cache error
does not undo completed work, and a failed challenge can have partially
removed data or files. The command rolls back only uncommitted database work,
continues after individual exceptions, and returns nonzero for deletion or
cache-refresh failures. It attempts both challenge and standings cache clears
after deletion attempts, even after a failure. If only cache refresh failed,
the successful database deletions remain committed.

Avoid concurrent edits or deletions while using this command. The command
rechecks each target's ID, name, and type before deletion and reports a changed
target as failed rather than deleting the changed record.

IDs are permanent database identifiers, not list row numbers or display
positions. The command never renumbers challenges or resets the ID counter;
gaps are expected. Use Position to control the player-facing challenge order.

This command is not a Monthly Game reset. It does not rewrite closed monthly
snapshots or revoke standalone CTFd Awards, including first-solver bonus
Awards. Those can remain after their original challenge is deleted. Review
them separately if the intention is to reset all scores.

## Permissions

Push Challenges writes no plugin-owned files and has no writable directory.
The command identity needs read permission on the manifest and execute/traverse
permission on all parent directories. Mode `0640` with a CTFd-readable group is
appropriate for the manifest; a dedicated parent directory commonly uses
`0750`.

The command inherits database credentials and authorization from CTFd's normal
environment. Do not place credentials or server configuration in the workbook
or manifest.
Deletion also needs permission to remove files from CTFd's existing upload
storage. See [Filesystem permissions](installation.md#filesystem-permissions).
