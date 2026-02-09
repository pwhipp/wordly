from __future__ import annotations

import io
import json
import sys
import urllib.error
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

import app as app_module  # noqa: E402


class DummyResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> "DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    candidate_path = tmp_path / "candidate_words.txt"
    candidate_path.write_text("crate A container.\n", encoding="utf-8")
    admin_code_path = tmp_path / "admin_code.txt"
    admin_code_path.write_text("FSQ2023", encoding="utf-8")
    state_path = tmp_path / "game_state.json"
    state_path.write_text(
        json.dumps(
            {
                "word": "CRATE",
                "definition": "A container.",
                "scores": [],
                "players": {},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.ADMIN_CODE_FILE", admin_code_path)
    monkeypatch.setattr("app.CANDIDATE_WORDS_FILE", candidate_path)
    monkeypatch.setattr("app.GAME_STATE_FILE", state_path)
    app_module.app.config.update({"TESTING": True})
    with app_module.app.test_client() as test_client:
        yield test_client


def test_guess_evaluation(client, monkeypatch):
    monkeypatch.setattr(
        "app.urllib.request.urlopen",
        lambda *args, **kwargs: DummyResponse(),
    )
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
    state = json.loads(app_module.GAME_STATE_FILE.read_text(encoding="utf-8"))
    assert state["scores"][0]["uid"] == "abc"


def test_submit_score_requires_name(client):
    response = client.post(
        "/api/submit",
        json={"uid": "abc", "tries": 3, "duration": 30},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "name must be a string"


def test_guess_rejected_when_not_a_word(client, monkeypatch):
    def raise_not_found(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://api.dictionaryapi.dev/api/v2/entries/en/xxxxx",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    monkeypatch.setattr("app.urllib.request.urlopen", raise_not_found)
    response = client.post("/api/guess", json={"guess": "xxxxx"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "That is not a word."


def test_guess_accepted_when_api_unreachable(client, monkeypatch):
    def raise_unreachable(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("app.urllib.request.urlopen", raise_unreachable)
    response = client.post("/api/guess", json={"guess": "crate"})
    assert response.status_code == 200


def test_dictionary_lookup_url_encoded(monkeypatch):
    captured = {}

    def capture_request(request, timeout=2):
        captured["url"] = request.full_url
        return DummyResponse()

    monkeypatch.setattr("app.urllib.request.urlopen", capture_request)
    assert app_module.is_valid_word("c++") is True
    assert captured["url"].endswith("/c%2B%2B")


def test_state_persistence(client):
    payload = {
        "uid": "user-1",
        "name": "Sam",
        "state": {
            "grid": [[{"letter": "C", "status": "correct"}]],
            "currentRow": 1,
            "currentCol": 0,
            "keyboardStatuses": {"C": "correct"},
            "gameOver": False,
            "isWinner": False,
            "startTime": 12345,
            "maxGuesses": 6,
            "wordLength": 5,
        },
    }
    response = client.post("/api/state", json=payload)
    assert response.status_code == 200
    stored = app_module.GAME_STATE_FILE.read_text(encoding="utf-8")
    assert stored.index('"name"') < stored.index('"grid"')

    fetched = client.get("/api/state?uid=user-1")
    assert fetched.status_code == 200
    assert fetched.get_json()["state"]["name"] == "Sam"


def test_state_name_conflict(client):
    first = {
        "uid": "user-1",
        "name": "Alex",
        "state": {"currentRow": 0},
    }
    second = {
        "uid": "user-2",
        "name": "Alex",
        "state": {"currentRow": 1},
    }
    response = client.post("/api/state", json=first)
    assert response.status_code == 200
    conflict = client.post("/api/state", json=second)
    assert conflict.status_code == 409
    assert (
        conflict.get_json()["error"]
        == "The name Alex is already in use. Please choose another"
    )


def test_admin_verification(client):
    response = client.post("/api/admin/verify", json={"code": "FSQ2023"})
    assert response.status_code == 200
    assert response.get_json()["valid"] is True


def test_admin_reset_clears_state(client):
    client.post(
        "/api/submit",
        json={"uid": "abc", "name": "Tester", "tries": 3, "duration": 30},
    )
    response = client.post("/api/admin/reset", json={"code": "FSQ2023"})
    assert response.status_code == 200
    state = json.loads(app_module.GAME_STATE_FILE.read_text(encoding="utf-8"))
    assert state["scores"] == []
    assert state["players"] == {}
