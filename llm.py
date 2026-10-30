"""The one door to the LLM provider (spec.md "LLM layer (Level 2)").

- Exactly two call types, CALL_TYPES; anything else is refused here.
- Provider: Anthropic. Swapping providers means changing this file only.
- The API key comes from the ANTHROPIC_API_KEY environment variable (a
  Fly secret in production), never from code or a tracked file. No key
  → LLMUnavailable, and callers show their template version.
- Per-user daily caps, stored in llm_usage and taken *before* the request
  in one transaction, so retries and double-clicks can't exceed them.
- One request, one reply: no chat, no tools, no memory between calls.
- Nothing about the payload or the reply is logged — only the call type
  and the kind of failure.

Callers build the payload (phase_guide.payload(), week_fit.payload()) and
validate the reply; this module only sends JSON and parses JSON.
"""
import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

import anthropic

MODEL = "claude-opus-5-5"  # claude-haiku-5-5 is ~40× cheaper — the owner's call (DECISIONS.md)
EFFORT = "low"
MAX_TOKENS = 8000  # Opus 5.5 always thinks; the room covers thinking + a short JSON reply
TIMEOUT_SECONDS = 60
MAX_RETRIES = 1
API_KEY_ENV = "ANTHROPIC_API_KEY"
CALL_TYPES = ("phase_guide", "week_fit")
DAILY_CAPS = {"phase_guide": 3, "week_fit": 5}
# Server-side fallback: if the model declines, Anthropic retries on another
# Claude model inside the same request (never leaves Anthropic).
FALLBACK_BETA = "server-side-fallback-2026-07-01"

log = logging.getLogger("nova.llm")
# The SDK logs whole request bodies at DEBUG (and httpx2 logs URLs at INFO).
# Pin both to WARNING so a debug-level root logger (or ANTHROPIC_LOG=debug)
# can never write a payload or note to the logs.
for _name in ("anthropic", "httpx2", "httpx"):
    logging.getLogger(_name).setLevel(logging.WARNING)

# Tests inject an HTTP client with a mock transport here; None = the SDK's own.
_http_client = None


class LLMUnavailable(Exception):
    """The call didn't happen or didn't produce usable JSON. The message is
    short and safe to show; callers fall back to their template."""


class CapReached(LLMUnavailable):
    pass


def set_http_client(client) -> None:
    global _http_client
    _http_client = client


def has_key() -> bool:
    return bool(os.environ.get(API_KEY_ENV, "").strip())


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def usage_today(conn: sqlite3.Connection, user_id: int, call_type: str) -> int:
    row = conn.execute(
        "SELECT count FROM llm_usage WHERE user_id = ? AND day = ? AND call_type = ?",
        (user_id, _today(), call_type),
    ).fetchone()
    return row[0] if row else 0


def remaining_today(conn: sqlite3.Connection, user_id: int, call_type: str) -> int:
    return max(0, DAILY_CAPS[call_type] - usage_today(conn, user_id, call_type))


def _take_slot(conn: sqlite3.Connection, user_id: int, call_type: str) -> None:
    """Count this attempt, or raise CapReached. One transaction, so two
    concurrent requests can't both take the last slot."""
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO llm_usage (user_id, day, call_type, count) VALUES (?, ?, ?, 0)",
            (user_id, _today(), call_type),
        )
        cur = conn.execute(
            "UPDATE llm_usage SET count = count + 1"
            " WHERE user_id = ? AND day = ? AND call_type = ? AND count < ?",
            (user_id, _today(), call_type, DAILY_CAPS[call_type]),
        )
        if cur.rowcount == 0:
            raise CapReached("You've reached today's limit for this — it resets tomorrow.")


def request(
    conn: sqlite3.Connection, user_id: int, call_type: str,
    system: str, payload: dict, schema: dict,
) -> dict:
    """Send one JSON payload, get one JSON object back (shaped by `schema`).

    Raises LLMUnavailable (or CapReached) instead of returning anything
    partial. The caller validates the content.
    """
    if call_type not in CALL_TYPES:
        raise ValueError(f"unknown LLM call type {call_type!r}; only {CALL_TYPES}")
    if not has_key():
        raise LLMUnavailable("The writing assistant isn't set up on this server.")
    _take_slot(conn, user_id, call_type)
    client = anthropic.Anthropic(
        api_key=os.environ[API_KEY_ENV].strip(), http_client=_http_client,
        max_retries=MAX_RETRIES, timeout=TIMEOUT_SECONDS,
    )
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, sort_keys=True)}],
            output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema}},
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AnthropicError as exc:
        log.warning("llm %s failed: %s", call_type, type(exc).__name__)
        raise LLMUnavailable("The writing assistant couldn't be reached just now.") from None
    if response.stop_reason != "end_turn":
        log.warning("llm %s stopped: %s", call_type, response.stop_reason)
        raise LLMUnavailable("The writing assistant didn't finish a reply.")
    text = next((b.text for b in response.content if b.type == "text"), None)
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        log.warning("llm %s returned no JSON", call_type)
        raise LLMUnavailable("The writing assistant's reply couldn't be read.") from None
    if not isinstance(data, dict):
        raise LLMUnavailable("The writing assistant's reply couldn't be read.")
    log.info("llm %s ok", call_type)
    return data
