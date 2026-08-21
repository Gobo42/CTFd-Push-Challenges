import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_DOCS = (
    ROOT / "README.md",
    ROOT / "docs/installation.md",
    ROOT / "docs/operator-guide.md",
    ROOT / "docs/troubleshooting.md",
    ROOT / "docs/workbook-authoring.md",
    ROOT / "docs/csv-format.md",
)


def test_public_documentation_links_resolve():
    for path in PUBLIC_DOCS:
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if target.startswith(("http://", "https://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.exists(), f"{path}: missing {target}"


def test_installation_documents_complete_ctfd_cli_execution_context():
    installation = (ROOT / "docs/installation.md").read_text(encoding="utf-8")
    required = (
        "exec systemd-run --pty --uid=ctfd --gid=ctfd",
        "--property=EnvironmentFile=/etc/ctfd/ctfd.env",
        "--working-directory=/opt/CTFd",
        '/opt/CTFd/.venv/bin/flask "$@"',
        "operator-owned",
        "does not package",
        "/srv/ctfd-imports/challenges.push.json",
        "ctfd-cli push-challenges --help",
        "ctfd-cli push-challenges import --help",
    )
    for value in required:
        assert value in installation, f"installation guide missing {value}"


def test_operator_guide_dry_runs_and_applies_the_same_manifest():
    operator = (ROOT / "docs/operator-guide.md").read_text(encoding="utf-8")
    normalized = " ".join(operator.split())
    manifest = "/srv/ctfd-imports/challenges.push.json"

    assert operator.count(manifest) >= 2
    assert f"ctfd-cli push-challenges import {manifest}" in operator
    assert f"{manifest} --apply" in operator
    assert "exact same manifest" in normalized
    assert "nonzero" in operator


def test_troubleshooting_covers_launcher_configuration_and_manifest_access():
    troubleshooting = (ROOT / "docs/troubleshooting.md").read_text(
        encoding="utf-8"
    )
    required = (
        "No such command",
        "EnvironmentFile",
        "Worker failed to boot",
        "Permission denied",
        "does not exist",
        "systemd-run",
        "journalctl",
        "stat -c",
        "namei -l",
        "Do not print the environment file",
    )
    normalized = " ".join(troubleshooting.split())
    for value in required:
        assert value in normalized, f"troubleshooting guide missing {value}"
