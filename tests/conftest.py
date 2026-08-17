import json
import sys
from pathlib import Path

import pytest
from tests.helpers import create_ctfd, destroy_ctfd

sys.path.insert(0, str(Path(__file__).resolve().parent / "plugin"))
from plugin_loader import load_plugin  # noqa: E402


def challenge_data(name="Example", next_name=None):
    return {
        "name": name,
        "description": "Prompt",
        "value": 100,
        "category": "Web",
        "state": "hidden",
        "type": "standard",
        "logic": "any",
        "max_attempts": 0,
        "attribution": "",
        "connection_info": "",
        "tags": ["beginner"],
        "next": next_name,
        "solution": {"action": "preserve", "content": None, "state": None},
        "flags": [],
        "hints": [],
    }


def manifest_data(*challenges, warnings=None):
    return {
        "format": "push-challenges",
        "version": 1,
        "warnings": warnings or [],
        "challenges": list(challenges or (challenge_data(),)),
    }


@pytest.fixture
def app():
    application = create_ctfd()
    load_plugin(application)
    with application.app_context():
        yield application
    destroy_ctfd(application)


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


@pytest.fixture
def manifest_path(tmp_path):
    path = tmp_path / "challenges.push.json"
    path.write_text(json.dumps(manifest_data()), encoding="utf-8")
    return path


@pytest.fixture
def write_manifest(tmp_path):
    def write(data):
        path = tmp_path / "challenges.push.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return write
