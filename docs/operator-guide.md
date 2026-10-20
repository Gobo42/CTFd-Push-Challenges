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

## Preserved data

The importer never deletes:

- challenges;
- hints;
- solution records;
- challenge or solution file records;
- stored files.

It does not modify attachments, solves, submissions, attempts, challenge
requirements, module membership, position, or fields outside the supported
manifest. Hint updates preserve hint IDs and unlock/payment history. Solution
updates preserve the solution ID and attachment links.

## Transactions and failures

All challenge, Dynamic scoring, bonus configuration, flag, tag, solution, hint,
requirement, and hierarchy changes in the eligible subset
use one ORM transaction and one commit. Any failure before commit rolls back
the complete import and returns nonzero. Add `--debug` only when an unexpected
exception traceback is needed.

After commit, the command clears CTFd challenge and standings caches. A cache
failure is printed as a post-commit warning. That warning means the database
transaction succeeded; it must not be interpreted as a rollback.

## Permissions

Push Challenges writes no plugin-owned files and has no writable directory.
The command identity needs read permission on the manifest and execute/traverse
permission on all parent directories. Mode `0640` with a CTFd-readable group is
appropriate for the manifest; a dedicated parent directory commonly uses
`0750`.

The command inherits database credentials and authorization from CTFd's normal
environment. Do not place credentials or server configuration in the workbook
or manifest.
