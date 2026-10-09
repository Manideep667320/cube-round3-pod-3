"""Damage-path tests with a STUBBED provider (no credentials needed).

These verify the code around the model call — strict JSON extraction, pydantic
validation, one retry, the sha256 cache, and the fail-safe — so that adding a real
key later only exercises the network, not untested glue.
"""
import io
import json

import httpx
import pytest
from PIL import Image, ImageDraw

from agents.receiving import config, damage, db


@pytest.fixture()
def agent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "receiving.db")
    monkeypatch.setattr(config, "MEDIA_DIR", tmp_path / "media")
    monkeypatch.setattr(config, "vlm_config",
                        lambda: {"provider": "openai", "api_key": "test-key",
                                 "model": "test-model"})
    db.init_db()
    return tmp_path


def photo(tmp_path) -> str:
    path = tmp_path / "label.jpg"
    img = Image.new("RGB", (320, 240), (190, 170, 145))
    ImageDraw.Draw(img).rectangle([20, 20, 300, 220], outline=(90, 70, 50), width=4)
    img.save(path, quality=88)
    return str(path)


class FakeResponse:
    def __init__(self, payload: dict, error: Exception | None = None):
        self._payload = payload
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error

    def json(self):
        return self._payload


def openai_reply(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


GOOD = json.dumps({"damaged": True, "type": "crush", "severity": 4,
                   "confidence": 0.91, "description": "corners crushed"})


def stub_post(monkeypatch, replies: list, calls: list | None = None):
    """Each call pops the next reply; records how many calls were made."""
    record = calls if calls is not None else []

    def fake(url, **kwargs):
        record.append(url)
        item = replies[min(len(record) - 1, len(replies) - 1)]
        if isinstance(item, Exception):
            raise item
        return FakeResponse(item)

    monkeypatch.setattr(damage.httpx, "post", fake)
    return record


def test_html_free_json_extraction():
    assert damage._extract_json("```json\n{\"a\": 1}\n```") == {"a": 1}
    assert damage._extract_json("prose before {\"a\": 2} after") == {"a": 2}
    with pytest.raises(ValueError):
        damage._extract_json("no json here")


def test_no_photos_is_no_input(agent):
    result = damage.assess([], [])
    assert result["source"] == "no_input" and result["conf"] == 0.0


def test_missing_credentials_fail_safe(agent, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "vlm_config",
                        lambda: {"provider": None, "api_key": None, "model": None})
    path = photo(tmp_path)
    result = damage.assess([path], ["a" * 64])
    assert result["source"] == "unavailable" and result["conf"] == 0.0
    assert "credentials" in result["error"]


def test_valid_reply_is_parsed_and_cached(agent, monkeypatch, tmp_path):
    path = photo(tmp_path)
    sha = "b" * 64
    calls = stub_post(monkeypatch, [openai_reply(GOOD)])

    first = damage.assess([path], [sha])
    assert first["source"] == "vlm" and first["type"] == "crush"
    assert first["severity"] == 4 and first["conf"] == 0.91
    assert first["cached"] is False and len(calls) == 1

    second = damage.assess([path], [sha])          # same bytes -> cache, no new call
    assert second["cached"] is True and len(calls) == 1
    assert second["severity"] == 4

    fresh = damage.assess([path], ["c" * 64])      # new bytes -> new call
    assert fresh["cached"] is False and len(calls) == 2


def test_invalid_then_valid_retries_once(agent, monkeypatch, tmp_path):
    path = photo(tmp_path)
    calls = stub_post(monkeypatch, [openai_reply("not json at all"), openai_reply(GOOD)])
    result = damage.assess([path], ["d" * 64])
    assert result["source"] == "vlm" and len(calls) == 2


def test_schema_violation_is_treated_as_invalid(agent, monkeypatch, tmp_path):
    path = photo(tmp_path)
    bad = json.dumps({"damaged": True, "type": "banana", "severity": 9,
                      "confidence": 2.0, "description": "nonsense"})
    calls = stub_post(monkeypatch, [openai_reply(bad)])
    result = damage.assess([path], ["e" * 64])
    assert result["source"] == "unavailable" and len(calls) == 2   # tried twice, never trusted


def test_provider_error_fails_safe_without_raising(agent, monkeypatch, tmp_path):
    path = photo(tmp_path)
    calls = stub_post(monkeypatch, [httpx.ConnectError("boom")])
    result = damage.assess([path], ["f" * 64])
    assert result["source"] == "unavailable"
    assert "ConnectError" in result["error"] and len(calls) == 2
    assert result["damaged"] is False and result["severity"] == 0   # nothing invented


def test_cache_never_holds_handwritten_results(agent, monkeypatch, tmp_path):
    """Only validated model output reaches the cache (plan W3)."""
    path = photo(tmp_path)
    stub_post(monkeypatch, [openai_reply(GOOD)])
    damage.assess([path], ["1" * 64])
    import sqlite3
    with db.connect() as conn:
        rows = conn.execute("SELECT result, model FROM damage_cache").fetchall()
    assert len(rows) == 1
    cached = json.loads(rows[0]["result"])
    assert cached["model"] == "test-model" and cached["severity"] == 4
    assert rows[0]["model"] == "test-model"
