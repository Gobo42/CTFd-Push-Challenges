import json
import re

import pytest
from CTFd.models import Challenges, db
from tests.helpers import gen_user, login_as_user


def populate_challenges():
    for name, category, position, value in (
        ("Web second", "Web", 20, 5),
        ("Crypto automatic", "Crypto", 0, 1),
        ("Web first", "Web", 10, 500),
        ("Crypto first", "Crypto", 10, 100),
        ("Web tied position", "Web", 20, 2),
        ("Crypto second", "Crypto", 20, 50),
        ("Web automatic", "Web", 0, 0),
        ("Web added later", "Web", 50, 10),
    ):
        db.session.add(
            Challenges(
                name=name,
                category=category,
                position=position,
                value=value,
                state="hidden",
                type="standard",
            )
        )
    db.session.commit()


def page_config(response):
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(
        r'<script id="push-challenges-admin-order-data" '
        r'type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    assert match is not None, "Admin list must supply the optional ordering data"
    return json.loads(match[1]), html


def test_admin_list_supplies_category_position_order_without_reordering_html(app):
    populate_challenges()
    client = login_as_user(app, name="admin")
    config, html = page_config(client.get("/admin/challenges"))
    assert config["order"] == [4, 6, 2, 3, 5, 1, 8, 7]
    assert re.findall(r'data-challenge-id="(\d+)"', html) == [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
    ]
    assert "/plugins/push-challenges/assets/admin-order.js" in html
    assert Challenges.query.count() == 8


def test_grouped_order_preserves_existing_admin_search_filters(app):
    populate_challenges()
    client = login_as_user(app, name="admin")
    config, html = page_config(client.get("/admin/challenges?field=category&q=Web"))
    assert config["order"] == [3, 5, 1, 8, 7]
    assert re.findall(r'data-challenge-id="(\d+)"', html) == ["1", "3", "5", "7", "8"]


def test_admin_order_data_and_asset_support_subpath_installations(app):
    client = login_as_user(app, name="admin")
    config, html = page_config(
        client.get("/admin/challenges", environ_overrides={"SCRIPT_NAME": "/ctf"})
    )
    assert config["storageKey"].endswith(":/ctf")
    assert 'src="/ctf/plugins/push-challenges/assets/admin-order.js"' in html


@pytest.mark.parametrize("path", ["/admin/pages", "/admin/challenges/new", "/login"])
def test_unrelated_pages_do_not_load_admin_order_ui(app, path):
    client = login_as_user(app, name="admin")
    response = client.get(path)
    assert "push-challenges-admin-order-data" not in response.get_data(as_text=True)
    assert "/plugins/push-challenges/assets/admin-order.js" not in response.get_data(
        as_text=True
    )


def test_ordering_asset_is_admin_only_and_served_from_plugin_checkout(app):
    path = "/plugins/push-challenges/assets/admin-order.js"
    assert app.test_client().get(path).status_code in (302, 403)
    gen_user(db, name="player", email="player@example.com")
    player = login_as_user(app, name="player")
    assert player.get(path).status_code in (302, 403)
    admin = login_as_user(app, name="admin")
    response = admin.get(path)
    assert response.status_code == 200
    assert "javascript" in response.content_type


def test_loading_plugin_again_does_not_duplicate_admin_order_ui(app):
    from plugin_loader import load_plugin

    load_plugin(app)
    admin = login_as_user(app, name="admin")
    _, html = page_config(admin.get("/admin/challenges"))
    assert html.count('id="push-challenges-admin-order-data"') == 1


def test_adding_control_does_not_run_existing_context_processors_again(app):
    calls = []

    @app.context_processor
    def count_renders():
        calls.append(1)
        return {}

    admin = login_as_user(app, name="admin")
    calls.clear()
    page_config(admin.get("/admin/challenges"))
    assert len(calls) == 1
