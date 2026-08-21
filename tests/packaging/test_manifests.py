import re
import subprocess
import tarfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]

SERVER_FILES = {
    "README.md",
    "__init__.py",
    "cli.py",
    "importer.py",
    "docs/csv-format.md",
    "docs/installation.md",
    "docs/operator-guide.md",
    "docs/troubleshooting.md",
    "docs/workbook-authoring.md",
    "push_challenges_core/__init__.py",
    "push_challenges_core/errors.py",
    "push_challenges_core/graph.py",
    "push_challenges_core/manifest.py",
    "push_challenges_core/model.py",
    "push_challenges_core/tags.py",
}
TOOLS_FILES = {
    "README.md",
    "requirements-tools.txt",
    "authoring/__init__.py",
    "authoring/csv_input.py",
    "authoring/normalize.py",
    "authoring/preview.py",
    "authoring/workbook.py",
    "authoring/xlsx_input.py",
    "docs/csv-format.md",
    "docs/installation.md",
    "docs/operator-guide.md",
    "docs/troubleshooting.md",
    "docs/workbook-authoring.md",
    "push_challenges_core/__init__.py",
    "push_challenges_core/errors.py",
    "push_challenges_core/graph.py",
    "push_challenges_core/manifest.py",
    "push_challenges_core/model.py",
    "push_challenges_core/tags.py",
    "tools/create_workbook.py",
    "tools/push-challenges-template.xlsx",
    "tools/validate_challenges.py",
}


def archive_files(path, root):
    with tarfile.open(path, "r:gz") as archive:
        names = {
            member.name.removeprefix(f"{root}/")
            for member in archive.getmembers()
            if member.isfile()
        }
        roots = {member.name.split("/", 1)[0] for member in archive.getmembers()}
    return names, roots


def archive_markdown_links(path, member):
    with tarfile.open(path, "r:gz") as archive:
        content = archive.extractfile(member).read().decode("utf-8")
    return {
        target.split("#", 1)[0]
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", content)
        if not target.startswith(("http://", "https://", "#"))
    }


def test_shared_packager_builds_exact_server_and_tools_archives():
    result = subprocess.run(
        [WORKSPACE / "package-plugins.sh", "push-challenges"],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    server, server_roots = archive_files(
        WORKSPACE / "push-challenges.tar.gz", "push-challenges"
    )
    tools, tools_roots = archive_files(
        WORKSPACE / "push-challenges-tools.tar.gz",
        "push-challenges-tools",
    )
    assert server_roots == {"push-challenges"}
    assert tools_roots == {"push-challenges-tools"}
    assert server == SERVER_FILES
    assert tools == TOOLS_FILES
    assert archive_markdown_links(
        WORKSPACE / "push-challenges-tools.tar.gz",
        "push-challenges-tools/README.md",
    ) <= tools
    assert not any(
        part in server
        for part in (
            "requirements-tools.txt",
            "authoring/workbook.py",
            "tools/push-challenges-template.xlsx",
        )
    )
