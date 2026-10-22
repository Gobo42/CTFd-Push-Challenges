"""Optional browser-local ordering for CTFd's existing admin challenge list."""

import re
from pathlib import Path

from CTFd.models import Challenges
from CTFd.utils.decorators import admins_only
from flask import current_app, request, send_file, url_for

ASSET = Path(__file__).parent / "assets" / "admin-order.js"
FRAGMENT = (
    '<script id="push-challenges-admin-order-data" type="application/json">'
    "{{ config | tojson }}</script>"
    '<script defer src="{{ asset_url }}"></script>'
)


def _inject_control(response):
    if (
        request.endpoint != "admin.challenges_listing"
        or response.status_code != 200
        or response.mimetype != "text/html"
    ):
        return response
    html = response.get_data(as_text=True)
    if "</body>" not in html:
        return response
    visible_ids = [
        int(value) for value in re.findall(r'data-challenge-id="([0-9]+)"', html)
    ]
    ordered = (
        Challenges.query.with_entities(Challenges.id)
        .filter(Challenges.id.in_(visible_ids))
        .order_by(
            Challenges.category,
            (Challenges.position == 0).asc(),
            Challenges.position,
            Challenges.value,
            Challenges.id,
        )
        .all()
    )
    config = {
        "order": [challenge.id for challenge in ordered],
        "storageKey": "push-challenges:admin-category-position:"
        + (request.script_root or "/"),
    }
    fragment = current_app.jinja_env.from_string(FRAGMENT).render(
        config=config,
        asset_url=url_for("push_challenges_admin_order_asset"),
    )
    before, after = html.rsplit("</body>", 1)
    response.set_data(before + fragment + "</body>" + after)
    return response


@admins_only
def _serve_script():
    return send_file(ASSET, mimetype="text/javascript", max_age=3600)


def register_admin_order(app):
    """Add the opt-in control without replacing CTFd routes or templates."""
    if app.extensions.get("push_challenges_admin_order"):
        return
    app.add_url_rule(
        "/plugins/push-challenges/assets/admin-order.js",
        endpoint="push_challenges_admin_order_asset",
        view_func=_serve_script,
    )
    app.after_request(_inject_control)
    app.extensions["push_challenges_admin_order"] = True
