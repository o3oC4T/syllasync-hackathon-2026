"""Protect server credentials at the Streamlit browser boundary."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_server_key_is_never_sent_as_widget_default(monkeypatch):
    server_key = "server-only-test-placeholder"
    monkeypatch.setenv("UPSTAGE_API_KEY", server_key)
    app = AppTest.from_file(str(Path(__file__).parents[1] / "app.py"))
    app.run(timeout=30)

    assert not app.exception
    key_input = next(item for item in app.text_input if item.label == "Upstage API Key")
    assert key_input.value == ""
    assert server_key not in str(app)

    key_input.set_value("session-only-test-placeholder").run(timeout=30)
    assert not app.exception
    key_input = next(item for item in app.text_input if item.label == "Upstage API Key")
    assert key_input.value == "session-only-test-placeholder"
    assert server_key not in str(app)
