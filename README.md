# Push Challenges

Push Challenges provides a CTFd plugin and independent authoring
tools for creating or overwriting Standard and Dynamic challenges in bulk.
The server plugin also provides challenge-listing and interactive bulk
hide, unhide, and deletion commands for administrators.

Challenge authors can work in the included macro-free Excel workbook or in a
strict CSV file. The standalone validator prints every decoded challenge and
exports a versioned JSON manifest. An operator transfers that manifest to the
CTFd server, reviews a dry run, and adds `--apply` to commit it.

```bash
python3 tools/validate_challenges.py challenges.xlsx \
  --output challenges.push.json

ctfd-cli push-challenges import /srv/ctfd-imports/challenges.push.json
ctfd-cli push-challenges import /srv/ctfd-imports/challenges.push.json --apply
```

`ctfd-cli` is an operator-owned launcher, not part of this plugin. The
documented Debian example uses a transient systemd unit to run CTFd's own Flask
executable as `ctfd:ctfd`, with the CTFd environment file and working
directory. Transfer and install the validator's output at the server path
before running these commands. See
[Installation](docs/installation.md#ctfd-cli-launcher) before server imports.

Standard challenges use fixed values. Dynamic challenges use CTFd's native
Linear or Logarithmic decay in individual or team installations. Optional
first-solver bonus tiers require an updated Monthly Game plugin, which supports
individual mode only. Blank Bonus Mode leaves existing bonus settings alone.
The plugin adds no public pages or APIs. Its optional admin sorting control
uses an administrator-only JavaScript asset. Imports do not create, remove,
or modify attached files; the separate deletion command performs CTFd's normal
cleanup.

Use the workbook's optional Position column to keep related challenges in
sequence regardless of point value. Blank preserves existing ordering; `0`
restores CTFd's automatic point ordering. See
[Set challenge display order](docs/workbook-authoring.md#set-challenge-display-order).

On the existing admin challenge list, **Group by category and position** is
unchecked by default. Enable it to group each category by Position; overlapping
positions across categories are valid. The choice is remembered only in that
browser. Turning it off restores the original CTFd order without changing IDs.
See [Admin list ordering](docs/operator-guide.md#admin-list-ordering).

## Packages

- `push-challenges.tar.gz` is the server plugin. Extract it in CTFd's plugins
  directory.
- `push-challenges-tools.tar.gz` contains the workbook, validator, exporter,
  workbook generator, and their separate `openpyxl` requirement.

The server plugin uses CTFd's installed dependencies and requires no additional
Python package.

## Documentation

- [Installation](docs/installation.md)
- [Workbook authoring](docs/workbook-authoring.md)
- [Scoring and first-solver bonuses, with worked examples](docs/scoring-guide.md)
- [CSV format](docs/csv-format.md)
- [Operator guide](docs/operator-guide.md)
- [Troubleshooting](docs/troubleshooting.md)

## Safety model

Imports default to dry-run. Exact, case-sensitive challenge names select overwrite
targets. The importer validates all references before writing, rejects circular
`Next` chains, and commits the eligible import once. An existing challenge with
a different type is skipped entirely, not converted. The final
`MANUAL ACTION REQUIRED` section lists every skip, even when the command exits
successfully. Other pre-commit failures roll back the transaction.

Imports never delete challenges, hints, solution records, or attachments. Flags
and tags for imported challenges are deliberately replaced. Existing hints
whose exact titles appear in the manifest are updated in place; other hints are
preserved.

The plugin writes no plugin-owned files and needs no writable plugin directory.
The CTFd service
account only needs read access to the manifest and traversal permission on its
parent directories for imports. Deletion uses CTFd's configured upload storage
and requires permission to remove its files.

## List or delete challenges

To list actual database IDs, or select challenges interactively for deletion:

```bash
ctfd-cli push-challenges list
ctfd-cli push-challenges delete
```

The delete command accepts IDs and inclusive ranges such as `47,49,55-58`,
previews the selection, and requires literal `yes`. It deletes serially using
CTFd's normal handlers, including associated data and attached files. Back up
the database and uploads first. Before the native handler runs, the plugin
removes the selected challenge's solution attachments, solution unlocks, and
solution record. Other challenges' solutions are untouched.
Completed deletions cannot be rolled back as
a batch. See [Delete challenges](docs/operator-guide.md#delete-challenges).

## Hide or unhide challenges

To change only challenge visibility, use the same ID/range syntax:

```bash
ctfd-cli push-challenges hide '47,49,55-58'
ctfd-cli push-challenges unhide '47,49,55-58'
```

Each command previews the selection and requires exact lowercase `yes`.
Omit the selection to list challenges and enter IDs interactively. `hide`
sets challenge state to `hidden`; `unhide` sets it to `visible`. Locked
challenges are skipped, and solutions keep their own visibility settings.
No solves, flags, hints, or attachments are removed. Unlike deletion, all
eligible visibility changes commit together. See
[Hide or unhide challenges](docs/operator-guide.md#hide-or-unhide-challenges).

## Acceptance test

From a source checkout, run the acceptance test:

```bash
pytest tests/acceptance/test_workflow.py -v
```

This test generates a temporary workbook, exports and dry-runs its manifest,
proves dry-run leaves the database empty, applies two linked challenges, and
repeats an exact-name overwrite without duplicating challenges or changing the
retained hint ID.

The full `pytest` suite also requires Node.js for the admin checkbox's
JavaScript behavior tests. Node.js is not a deployment dependency.
