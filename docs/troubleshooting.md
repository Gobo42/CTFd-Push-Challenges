# Troubleshooting

Start with safe launcher, service, plugin, and manifest checks:

```bash
command -v ctfd-cli
stat -c '%A %a %U:%G %n' /usr/local/bin/ctfd-cli
systemctl cat ctfd.service
systemctl status ctfd.service --no-pager
journalctl -u ctfd.service -n 100 --no-pager
stat -c '%A %a %U:%G %n' \
  /opt/CTFd/.venv/bin/flask \
  /opt/CTFd/CTFd/plugins/push-challenges/__init__.py \
  /srv/ctfd-imports/challenges.push.json
namei -l /srv/ctfd-imports/challenges.push.json
ctfd-cli push-challenges --help
```

Adapt `/opt/CTFd`, `/usr/local/bin/ctfd-cli`, and the manifest path to the
deployment. `stat` and `namei` inspect metadata and directory traversal
permissions. `systemctl cat` shows which configuration file the service uses.
Do not print the environment file, or use `cat`, `grep`, `echo`, or similar
commands to expose its contents.

The example `ctfd-cli` uses `systemd-run --pty`. It prints a transient unit name
and invocation ID. When that command fails, retain those identifiers and query
the matching journal, for example:

```bash
journalctl _SYSTEMD_INVOCATION_ID=INVOCATION_ID --no-pager
```

## Diagnostic table

| Symptom | Cause | Confirmation | Correction |
| --- | --- | --- | --- |
| `No such command 'push-challenges'` | The plugin directory is wrong, CTFd was not restarted, or plugin loading failed | Confirm the packaged `__init__.py` path, inspect the CTFd journal, and run `ctfd-cli push-challenges --help` | Install the complete server archive under `CTFd/plugins/push-challenges`, preserve read/traverse permissions, restart every CTFd worker, and repeat command discovery |
| `Worker failed to boot` or the launcher cannot import CTFd | The launcher uses the wrong working directory, virtual environment, application factory, or `EnvironmentFile` | Compare the operator-owned launcher with `systemctl cat ctfd.service`; inspect path metadata and the CTFd/transient-unit journal without printing configuration values | Make the launcher use the same service identity, application configuration, project root, and virtualenv as CTFd; Push Challenges does not supply a replacement launcher |
| Manifest `does not exist` | The transient `ctfd` process cannot traverse an administrator home, a hardened unit hides that home, or the path is wrong | Run `namei -l` and `stat` on the supplied path as metadata checks; compare it with the command argument | Install the manifest into a dedicated path such as `/srv/ctfd-imports/challenges.push.json` instead of weakening home-directory protections |
| `Permission denied` reading the plugin or manifest | The `ctfd` identity lacks directory traversal or file read permission | Compare the `ctfd` user/group with every component reported by `namei -l` and the final modes reported by `stat` | Use read-only plugin files, directories such as `0750`, and a manifest such as `root:ctfd` `0640`; grant only the required access |
| `systemd-run` reports a failed transient unit | Flask returned nonzero or systemd could not start the configured command | Read the command's unit name or invocation ID and inspect its journal; the launcher preserves the failure status | Correct the first reported launcher, application, manifest, validation, or database error, then repeat dry-run |
| Dry-run exits nonzero | Manifest validation or database preflight rejected the requested operation | Review every reported error and retained authoring warning; no import writes occur during dry-run | Correct and regenerate the manifest, install the new file, and dry-run that exact file again |
| Apply reports that the transaction rolled back | Validation, preflight, constraint, or database work failed before commit | Preserve the command output and transient-unit journal; verify that it explicitly reports rollback | Correct the underlying problem and repeat dry-run before another apply; do not assume a partial import succeeded |
| Apply reports a post-commit cache warning | Database commit succeeded but cache invalidation failed | The output explicitly distinguishes the warning from rollback | Treat the database import as committed, correct the CTFd cache problem, and verify affected challenges before deciding whether further action is needed |
| Paths copied from the `/opt/CTFd` example are missing | The documented Debian layout differs from this deployment | Compare launcher paths with the actual CTFd service definition and metadata | Adapt the operator-owned launcher and diagnostic paths together; do not install a second system Flask as a workaround |

## Information to retain

For an unresolved failure, retain:

- the Push Challenges and CTFd versions;
- whether command discovery, dry-run, or apply failed;
- the manifest SHA-256 digest, not its confidential challenge contents;
- the transient unit name and invocation ID;
- the command's diagnostics and relevant journal entries; and
- recent plugin, launcher, CTFd configuration, database, or cache changes.

Do not attach CTFd credentials, environment-file contents, database dumps, or
challenge flags to an ordinary support ticket.
