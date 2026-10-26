"""Shared fixtures."""
import socket

import pytest


class NetworkCallAttempted(AssertionError):
    pass


@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to open a network connection or
    resolve a hostname while it runs."""
    def refuse(*args, **kwargs):
        raise NetworkCallAttempted(f"network access attempted: {args!r}")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
