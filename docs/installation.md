# Installation

## Server plugin

Copy `push-challenges.tar.gz` to the CTFd server and extract it directly in the
directory CTFd uses for plugins. The archive creates its own
`push-challenges/` directory.

For a source installation whose plugin directory is
`/opt/CTFd/CTFd/plugins`, a typical command is:

```bash
cd /opt/CTFd/CTFd/plugins
sudo tar -xzf /path/to/push-challenges.tar.gz
```

Set ownership consistently with the other installed plugins. The plugin source
only needs to be readable by CTFd; it does not need to be writable.

```bash
sudo chown -R root:ctfd /opt/CTFd/CTFd/plugins/push-challenges
sudo find /opt/CTFd/CTFd/plugins/push-challenges -type d -exec chmod 0750 {} +
sudo find /opt/CTFd/CTFd/plugins/push-challenges -type f -exec chmod 0640 {} +
```

Replace `root:ctfd` and the path with values appropriate to the installation.
If CTFd runs under a different group, that group must be able to traverse the
directories and read the files.

Restart CTFd after initial installation or replacement so every worker loads
the same plugin code.

## CTFd CLI launcher

This deployment provides an operator-owned `ctfd-cli` command that runs Flask
with the same operating-system identity and application configuration as the
CTFd web service:

```bash
#!/bin/bash
# Run any flask/CTFd command as the ctfd service account with the
# service environment loaded — the same context the running service uses.
exec systemd-run --pty --uid=ctfd --gid=ctfd \
  --property=EnvironmentFile=/etc/ctfd/ctfd.env \
  --working-directory=/opt/CTFd \
  /opt/CTFd/.venv/bin/flask "$@"
```

Push Challenges does not package, install, or modify this launcher. The
example is specific to a Debian-style `/opt/CTFd` deployment and must match the
actual CTFd service account, environment file, working directory, virtual
environment, and application factory. Deployments using `config.ini`, a
container, another environment file, or a different project layout must use
their equivalent established launcher.

The important properties are independent of the script's name:

- the command runs as the same account and group as CTFd;
- it loads the same application configuration as CTFd;
- it starts in the CTFd project root;
- it invokes Flask from CTFd's virtual environment; and
- it propagates Flask's exit status through `exec` and `systemd-run`.

Do not display, source interactively, or copy the contents of
`/etc/ctfd/ctfd.env` during validation. The launcher passes it directly to the
transient systemd unit.

Verify launcher discovery and the plugin commands:

```bash
command -v ctfd-cli
ctfd-cli push-challenges --help
ctfd-cli push-challenges import --help
```

Each successful invocation prints the transient unit information and returns
exit status zero. `No such command 'push-challenges'` means the CTFd
application did not load this plugin; do not proceed to an import until command
discovery succeeds.

The server plugin has no separate Python requirements. Do not install the
authoring-only `requirements-tools.txt` into CTFd unless that is independently
desired.

## Authoring tools

The authoring tools can run on an administrator or author workstation and do
not need network access to CTFd.

```bash
tar -xzf push-challenges-tools.tar.gz
cd push-challenges-tools
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-tools.txt
```

Python 3.11 or later is recommended. The workbook is ordinary `.xlsx` and has
no macros.

The tools archive includes a ready-made workbook and a generator for creating a
fresh workbook with a chosen number of authoring rows:

```bash
python3 tools/create_workbook.py \
  --output push-challenges-template.xlsx
python3 tools/create_workbook.py \
  --output large-event.xlsx --rows 1000
```

`--output` is required. `--rows` defaults to `500` and must be at least `1`.
The selected row count is applied independently to the Challenges, Flags,
Solutions, and Hints tables. Generating to an existing path replaces that
workbook, so retain authored files under a different name.

## Filesystem permissions

The plugin has no cache, upload, database, log, or configuration directory of
its own. Nothing under `/var/lib`, `/var/log`, or the installed plugin
directory needs to be writable for Push Challenges.

The CTFd command process must be able to:

- traverse every parent directory of the supplied manifest;
- read the manifest file;
- access CTFd's database using CTFd's normal configuration.

For example, create a dedicated staging directory and install the exact
validated manifest for group `ctfd`:

```bash
sudo install -d -o root -g ctfd -m 0750 /srv/ctfd-imports
sudo install -o root -g ctfd -m 0640 \
  /path/to/validated/challenges.push.json \
  /srv/ctfd-imports/challenges.push.json
stat -c '%A %a %U:%G %n' \
  /srv/ctfd-imports /srv/ctfd-imports/challenges.push.json
```

If a launcher changes identity with `systemd-run`, remember that a manifest in
a private home directory may be unreadable even when the file itself is mode
`0644`; the service account also needs traversal permission on the home
directory. Prefer a dedicated import directory.

Run the default dry-run before adding `--apply`:

```bash
ctfd-cli push-challenges import /srv/ctfd-imports/challenges.push.json
```

See the [Operator Guide](operator-guide.md) for the review and apply workflow
and [Troubleshooting](troubleshooting.md) for launcher, configuration, and
permission failures.

## Upgrades

Replace the complete plugin directory from one archive and restart all CTFd
workers. Do not merge files from different releases. Push Challenges stores no
plugin-owned schema or state, so there is no plugin migration command.
