import asyncio
import contextlib
import importlib
import io
import sys
import types
from pathlib import Path

import pytest


def _install_fake_discord_module():
    """Install a minimal fake `discord` module into sys.modules for offline testing."""

    fake_discord = types.ModuleType("discord")

    class _Intents:
        def __init__(self):
            self.message_content = False

        @classmethod
        def default(cls):
            return cls()

    class _Client:
        def __init__(self, intents=None):
            self.intents = intents
            self.user = "TestBot"
            self._events = {}
            self.last_run_token = None

        def event(self, func):
            # Mirrors discord.py's decorator behavior enough for our tests.
            self._events[func.__name__] = func
            return func

        def run(self, token):
            # Never connect in unit tests.
            self.last_run_token = token

    fake_discord.Intents = _Intents
    fake_discord.Client = _Client

    sys.modules["discord"] = fake_discord


def _import_botmain_fresh():
    """Import/reload botmain after fake discord has been installed.

    Uses a file-based import so `pytest -q` works even if the repo root
    isn't on `sys.path`.
    """

    botmain_path = Path(__file__).resolve().parents[1] / "botmain.py"
    if not botmain_path.exists():
        raise FileNotFoundError(f"Expected botmain.py at: {botmain_path}")

    import importlib.util

    spec = importlib.util.spec_from_file_location("botmain", botmain_path)
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    sys.modules["botmain"] = module
    spec.loader.exec_module(module)
    return module

@pytest.fixture(autouse=True)
def _fake_discord_module():
    """Ensure `import botmain` never tries to import real discord.py during tests."""
    _install_fake_discord_module()


@pytest.fixture()
def botmain_module():
    return _import_botmain_fresh()


def test_load_quotes_missing_file_returns_empty_lists_and_prints(botmain_module, monkeypatch):
    def _raise_fnf(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr("builtins.open", _raise_fnf)

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        data = botmain_module.load_quotes()

    assert data == {"snark": [], "it_crowd": []}
    assert "quotes.json is missing" in buf.getvalue()


def test_load_quotes_invalid_json_returns_empty_lists_and_prints(botmain_module, monkeypatch):
    # Exercise the JSONDecodeError branch.
    monkeypatch.setattr("builtins.open", lambda *a, **k: io.StringIO("not-json"))
    monkeypatch.setattr(
        botmain_module.json,
        "load",
        lambda *_a, **_k: (_ for _ in ()).throw(botmain_module.json.JSONDecodeError("x", "y", 0)),
    )

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        data = botmain_module.load_quotes()

    assert data == {"snark": [], "it_crowd": []}
    assert "invalid JSON" in buf.getvalue()


def test_on_ready_prints_logged_in_user(botmain_module):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        asyncio.run(botmain_module.on_ready())

    assert "Logged in as TestBot" in buf.getvalue()


def test_on_message_ignores_own_messages(botmain_module):
    class _Channel:
        def __init__(self):
            self.sent = []

        async def send(self, content):
            self.sent.append(content)

    channel = _Channel()
    msg = types.SimpleNamespace(
        author=botmain_module.client.user,
        content="!printquote",
        channel=channel,
    )

    asyncio.run(botmain_module.on_message(msg))
    assert channel.sent == []


def test_on_message_snark_path_sends_quote(botmain_module, monkeypatch):
    class _Channel:
        def __init__(self):
            self.sent = []

        async def send(self, content):
            self.sent.append(content)

    botmain_module.quotes = {"snark": ["S1"], "it_crowd": ["I1"]}

    channel = _Channel()
    msg = types.SimpleNamespace(
        author="SomeoneElse",
        content="!printquote",
        channel=channel,
    )

    monkeypatch.setattr(botmain_module.random, "random", lambda: 0.0)
    monkeypatch.setattr(botmain_module.random, "choice", lambda seq: seq[0])

    asyncio.run(botmain_module.on_message(msg))
    assert channel.sent == ["S1"]


def test_on_message_it_crowd_path_sends_quote(botmain_module, monkeypatch):
    class _Channel:
        def __init__(self):
            self.sent = []

        async def send(self, content):
            self.sent.append(content)

    botmain_module.quotes = {"snark": ["S1"], "it_crowd": ["I1"]}

    channel = _Channel()
    msg = types.SimpleNamespace(
        author="SomeoneElse",
        content="!printquote",
        channel=channel,
    )

    monkeypatch.setattr(botmain_module.random, "random", lambda: 0.99)
    monkeypatch.setattr(botmain_module.random, "choice", lambda seq: seq[0])

    asyncio.run(botmain_module.on_message(msg))
    assert channel.sent == ["I1"]


def test_on_message_fallback_quote_when_key_missing(botmain_module, monkeypatch):
    class _Channel:
        def __init__(self):
            self.sent = []

        async def send(self, content):
            self.sent.append(content)

    # No "snark" key to force the default list in `quotes.get(...)`.
    botmain_module.quotes = {}

    channel = _Channel()
    msg = types.SimpleNamespace(
        author="SomeoneElse",
        content="!printquote",
        channel=channel,
    )

    monkeypatch.setattr(botmain_module.random, "random", lambda: 0.0)
    monkeypatch.setattr(botmain_module.random, "choice", lambda seq: seq[0])

    asyncio.run(botmain_module.on_message(msg))
    assert channel.sent == ["Your JSON is empty. Shame."]

