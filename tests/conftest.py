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


# --- Level 2: a fake LLM provider at the HTTP layer ----------------------------
# The real Anthropic SDK builds and "sends" the request; a MockTransport
# answers it. So tests see the exact request body that would leave the
# machine, and no socket is ever opened.

class FakeProvider:
    def __init__(self):
        self.requests: list[dict] = []
        self.reply = None  # dict → sent as the model's JSON text
        self.status = 200
        self.raw_text = None  # overrides `reply` with arbitrary text
        self.stop_reason = "end_turn"
        self.reply_fn = None  # payload dict → reply dict, for replies that depend on the request

    def handler(self, request):
        import json

        import httpx2

        self.requests.append(json.loads(request.content))
        if self.status != 200:
            return httpx2.Response(self.status, json={"type": "error", "error": {"type": "api_error", "message": "x"}})
        if self.reply_fn is not None:
            text = json.dumps(self.reply_fn(json.loads(self.requests[-1]["messages"][0]["content"])))
        else:
            text = self.raw_text if self.raw_text is not None else json.dumps(self.reply)
        return httpx2.Response(200, json={
            "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": self.stop_reason,
            "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
        })

    def user_payload(self, i: int = -1) -> dict:
        import json

        return json.loads(self.requests[i]["messages"][0]["content"])


@pytest.fixture
def fake_llm(monkeypatch, no_network):
    import anthropic
    import httpx2

    import llm

    fake = FakeProvider()
    monkeypatch.setenv(llm.API_KEY_ENV, "test-key-not-real")
    monkeypatch.setattr(llm, "MAX_RETRIES", 0)
    llm.set_http_client(anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(fake.handler)))
    yield fake
    llm.set_http_client(None)
