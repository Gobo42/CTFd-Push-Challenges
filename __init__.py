"""CTFd challenge import, maintenance, and optional admin list ordering."""


def load(app):
    """Register commands and the admin-only sorting asset; no writable state."""
    from .admin_order import register_admin_order
    from .cli import register_cli

    register_cli(app)
    register_admin_order(app)
