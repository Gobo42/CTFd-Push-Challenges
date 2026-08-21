# Push Challenges

Push Challenges provides a CLI-only CTFd plugin and independent authoring
tools for creating or overwriting standard challenges in bulk.

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

The first release supports fixed-value Standard challenges in individual or
team CTFd installations. Dynamic challenge input is recognized but rejected.
The plugin has no web routes and does not create, remove, or modify attached
files.

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
- [CSV format](docs/csv-format.md)
- [Operator guide](docs/operator-guide.md)
- [Troubleshooting](docs/troubleshooting.md)

## Safety model

Dry-run is the default. Exact, case-sensitive challenge names select overwrite
targets. The importer validates all references before writing, rejects circular
`Next` chains, and commits the complete import once. A pre-commit failure rolls
back the transaction.

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
