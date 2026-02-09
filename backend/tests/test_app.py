from __future__ import annotations

import io
import sys
import urllib.error
from pathlib import Path

import pytest
from sqlalchemy import select

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

import app as app_module  # noqa: E402
import db as db_module  # noqa: E402
import game_logic as logic_module  # noqa: E402
import game_store as store_module  # noqa: E402
from models import PlayerState, Score  # noqa: E402


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
    monkeypatch.setattr("app.ADMIN_CODE_FILE", admin_code_path)
    monkeypatch.setattr(logic_module, "CANDIDATE_WORDS_FILE", candidate_path)
    db_path = tmp_path / "wordly.sqlite"
    monkeypatch.setenv("WORDLY_DB_URL", f"sqlite:///{db_path}")
    db_module._ENGINE = None
    db_module._SESSIONMAKER = None
    db_module.configure_database()
    app_module.app.config.update({"TESTING": True})
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture()
def game_uid(client):
    response = client.get("/api/config")
    return response.get_json()["gameUid"]


def test_guess_evaluation(client, monkeypatch, game_uid):
    monkeypatch.setattr(
        "game_logic.urllib.request.urlopen",
        lambda *args, **kwargs: DummyResponse(),
    )
    response = client.post("/api/guess", json={"guess": "crate", "gameUid": game_uid})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["isCorrect"] is True
    assert payload["statuses"] == ["correct"] * 5


def test_submit_score(client, game_uid):
    response = client.post(
        "/api/submit",
        json={
            "uid": "abc",
            "name": "Tester",
            "tries": 3,
            "duration": 30,
            "gameUid": game_uid,
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["entry"]["tries"] == 3
    assert payload["entry"]["duration"] == 30
    with db_module.get_session() as session:
        score = session.scalar(
            select(Score).where(Score.uid == "abc")
        )
        assert score is not None
        assert score.uid == "abc"


def test_scores_sorted_by_tries_then_duration(client, game_uid):
    client.post(
        "/api/submit",
        json={
            "uid": "one",
            "name": "One",
            "tries": 3,
            "duration": 50,
            "gameUid": game_uid,
        },
    )
    client.post(
        "/api/submit",
        json={
            "uid": "two",
            "name": "Two",
            "tries": 2,
            "duration": 70,
            "gameUid": game_uid,
        },
    )
    client.post(
        "/api/submit",
        json={
            "uid": "three",
            "name": "Three",
            "tries": 3,
            "duration": 40,
            "gameUid": game_uid,
        },
    )

    response = client.get("/api/scores")
    assert response.status_code == 200
    payload = response.get_json()

    assert [entry["uid"] for entry in payload] == ["two", "three", "one"]


def test_submit_score_requires_name(client, game_uid):
    response = client.post(
        "/api/submit",
        json={"uid": "abc", "tries": 3, "duration": 30, "gameUid": game_uid},
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "name must be a string"


def test_submit_score_preserves_players(client, game_uid):
    response = client.post(
        "/api/state",
        json={
            "uid": "tom-1",
            "name": "Tom",
            "gameUid": game_uid,
            "state": {"currentRow": 2},
        },
    )
    assert response.status_code == 200

    score_response = client.post(
        "/api/submit",
        json={
            "uid": "sam-1",
            "name": "Sam",
            "tries": 4,
            "duration": 40,
            "gameUid": game_uid,
        },
    )
    assert score_response.status_code == 200

    tom_state = client.get("/api/state?uid=tom-1")
    assert tom_state.status_code == 200
    assert tom_state.get_json()["state"]["name"] == "Tom"


def test_guess_rejected_when_not_a_word(client, monkeypatch, game_uid):
    def raise_not_found(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="https://api.dictionaryapi.dev/api/v2/entries/en/xxxxx",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=io.BytesIO(b""),
        )

    monkeypatch.setattr("game_logic.urllib.request.urlopen", raise_not_found)
    response = client.post(
        "/api/guess", json={"guess": "xxxxx", "gameUid": game_uid}
    )
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "That is not a word."


def test_guess_accepted_when_api_unreachable(client, monkeypatch, game_uid):
    def raise_unreachable(*args, **kwargs):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("game_logic.urllib.request.urlopen", raise_unreachable)
    response = client.post("/api/guess", json={"guess": "crate", "gameUid": game_uid})
    assert response.status_code == 200


def test_dictionary_lookup_url_encoded(monkeypatch):
    captured = {}

    def capture_request(request, timeout=2):
        captured["url"] = request.full_url
        return DummyResponse()

    monkeypatch.setattr("game_logic.urllib.request.urlopen", capture_request)
    assert logic_module.is_valid_word("c++") is True
    assert captured["url"].endswith("/c%2B%2B")


def test_state_persistence(client, game_uid):
    payload = {
        "uid": "user-1",
        "name": "Sam",
        "gameUid": game_uid,
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
    with db_module.get_session() as session:
        record = session.scalar(
            select(PlayerState).where(PlayerState.uid == "user-1")
        )
        assert record is not None
        assert record.name == "Sam"
        assert record.state_data["currentRow"] == 1

    fetched = client.get("/api/state?uid=user-1")
    assert fetched.status_code == 200
    assert fetched.get_json()["state"]["name"] == "Sam"


def test_state_name_conflict(client, game_uid):
    first = {
        "uid": "user-1",
        "name": "Alex",
        "gameUid": game_uid,
        "state": {"currentRow": 0},
    }
    second = {
        "uid": "user-2",
        "name": "Alex",
        "gameUid": game_uid,
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


def test_admin_reset_clears_state(client, game_uid):
    with db_module.get_session() as session:
        original_game = store_module.get_active_game(session)
    client.post(
        "/api/submit",
        json={
            "uid": "abc",
            "name": "Tester",
            "tries": 3,
            "duration": 30,
            "gameUid": game_uid,
        },
    )
    response = client.post("/api/admin/reset", json={"code": "FSQ2023"})
    assert response.status_code == 200
    with db_module.get_session() as session:
        new_game = store_module.get_active_game(session)
        scores = session.scalars(
            select(Score).where(Score.game_id == new_game.id)
        ).all()
        players = session.scalars(
            select(PlayerState).where(PlayerState.game_id == new_game.id)
        ).all()
    assert scores == []
    assert players == []
    assert new_game.uid != original_game.uid


def test_config_includes_game_uid(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload["gameUid"], str)
    assert payload["gameUid"]


def test_guess_rejected_for_inactive_game(client, monkeypatch, game_uid):
    monkeypatch.setattr(
        "game_logic.urllib.request.urlopen",
        lambda *args, **kwargs: DummyResponse(),
    )
    client.post("/api/admin/reset", json={"code": "FSQ2023"})
    response = client.post("/api/guess", json={"guess": "crate", "gameUid": game_uid})
    assert response.status_code == 409
    payload = response.get_json()
    assert payload["nextGameUid"] != game_uid
