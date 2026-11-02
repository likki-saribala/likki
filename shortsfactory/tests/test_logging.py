import logging

from shortsfactory.__main__ import configure_logging


def test_http_client_loggers_stay_quiet_even_in_verbose_mode(caplog):
    """Pixabay's API key travels in the URL, so request logging must never be enabled."""
    configure_logging(verbose=True)
    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
