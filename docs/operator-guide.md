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
- retained authoring warnings.

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

An apply success returns zero. Verify the affected challenges in CTFd after
the command completes. A nonzero result means the transaction did not complete
unless the output explicitly identifies a post-commit cache warning. See
[Troubleshooting](troubleshooting.md).

## Matching and replacement rules

Challenge names and references are exact and case-sensitive. A matching
fixed-value Standard challenge is overwritten. No match creates a Standard
challenge. Multiple exact database matches are an error and include the
conflicting IDs. Existing Dynamic or otherwise non-static overwrite targets are
rejected.

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

All challenge, flag, tag, solution, hint, requirement, and hierarchy changes
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
