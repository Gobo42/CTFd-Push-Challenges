"""CLI-only CTFd challenge import plugin."""


def load(app):
    """Register the plugin without adding routes or writable state."""
    from .cli import register_cli

    register_cli(app)
