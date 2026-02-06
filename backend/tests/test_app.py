from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from app import app, SCORES_FILE  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    scores_path = tmp_path / "scores.json"
    scores_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr("app.SCORES_FILE", scores_path)
    app.config.update({"TESTING": True})
    with app.test_client() as test_client:
        yield test_client


def test_guess_evaluation(client):
    response = client.post("/api/guess", json={"guess": "crate"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isCorrect"] is True
    assert payload["statuses"] == ["correct"] * 5


def test_submit_score(client):
    response = client.post(
        "/api/submit",
        json={"uid": "abc", "name": "Tester", "tries": 3, "duration": 30},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["entry"]["score"] == 10.0
    scores = json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    assert scores[0]["uid"] == "abc"
