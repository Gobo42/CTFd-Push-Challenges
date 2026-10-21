# Push Challenges

Push Challenges provides a CLI-only CTFd plugin and independent authoring
tools for creating or overwriting Standard and Dynamic challenges in bulk.

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
The plugin has no web routes and does not create, remove, or modify attached
files.

Use the workbook's optional Position column to keep related challenges in
sequence regardless of point value. Blank preserves existing ordering; `0`
restores CTFd's automatic point ordering. See
[Set challenge display order](docs/workbook-authoring.md#set-challenge-display-order).

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

Dry-run is the default. Exact, case-sensitive challenge names select overwrite
targets. The importer validates all references before writing, rejects circular
`Next` chains, and commits the eligible import once. An existing challenge with
a different type is skipped entirely, not converted. The final
`MANUAL ACTION REQUIRED` section lists every skip, even when the command exits
successfully. Other pre-commit failures roll back the transaction.

Challenges, hints, solution records, and attachments are never deleted. Flags
and tags for imported challenges are deliberately replaced. Existing hints
whose exact titles appear in the manifest are updated in place; other hints are
preserved.

The plugin writes no files and needs no writable directory. The CTFd service
account only needs read access to the manifest and traversal permission on its
parent directories.

## Acceptance test

```bash
pytest tests/acceptance/test_workflow.py -v
```

This test generates a temporary workbook, exports and dry-runs its manifest,
proves dry-run leaves the database empty, applies two linked challenges, and
repeats an exact-name overwrite without duplicating challenges or changing the
retained hint ID.
