"""Shared fixtures."""
import socket

import pytest

# Loopback is allowed: on Windows, Python's asyncio event loop (used by
# Streamlit's AppTest) talks to itself over a 127.0.0.1 socket pair. That
# never leaves the machine; anything else is a real network call.
LOOPBACK = {"127.0.0.1", "::1", "localhost"}


class NetworkCallAttempted(AssertionError):
    pass


@pytest.fixture
def no_network(monkeypatch):
    """Fail the test if anything tries to reach beyond this machine (open a
    non-loopback connection or resolve a non-local hostname)."""
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_getaddrinfo = socket.getaddrinfo

    def _host(address):
        return address[0] if isinstance(address, tuple) else address

    def guard_connect(self, address):
        if _host(address) not in LOOPBACK:
            raise NetworkCallAttempted(f"network access attempted: {address!r}")
        return real_connect(self, address)

    def guard_connect_ex(self, address):
        if _host(address) not in LOOPBACK:
            raise NetworkCallAttempted(f"network access attempted: {address!r}")
        return real_connect_ex(self, address)

    def guard_getaddrinfo(host, *args, **kwargs):
        if host not in LOOPBACK and host is not None:
            raise NetworkCallAttempted(f"network access attempted: resolving {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    real_create_connection = socket.create_connection

    def guard_create_connection(address, *args, **kwargs):
        if _host(address) not in LOOPBACK:
            raise NetworkCallAttempted(f"network access attempted: {address!r}")
        return real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guard_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guard_connect_ex)
    monkeypatch.setattr(socket, "getaddrinfo", guard_getaddrinfo)
    monkeypatch.setattr(socket, "create_connection", guard_create_connection)
