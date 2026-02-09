from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

try:
    import sqlalchemy  # noqa: F401
except ModuleNotFoundError:
    SQLALCHEMY_AVAILABLE = False
else:
    SQLALCHEMY_AVAILABLE = True


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    candidate_path = tmp_path / "candidate_words.txt"
    candidate_path.write_text("crate A container.\n", encoding="utf-8")
    monkeypatch.setattr("game_logic.CANDIDATE_WORDS_FILE", candidate_path)
    db_path = tmp_path / "wordly.sqlite"
    monkeypatch.setenv("WORDLY_DB_URL", f"sqlite:///{db_path}")

    import db as db_module

    db_module._ENGINE = None
    db_module._SESSIONMAKER = None
    db_module.configure_database()
    with db_module.get_session() as session:
        yield session


@pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="sqlalchemy not installed")
def test_get_current_game_settings(db_session):
    import db as db_module

    settings = db_module.get_current_game_settings(db_session)
    assert settings["wordLength"] == 5
    assert settings["maxGuesses"] == db_module.DEFAULT_MAX_GUESSES
    assert settings["gameUid"]
    assert settings["word"] == "CRATE"
    assert settings["definition"] == "A container."


@pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="sqlalchemy not installed")
def test_list_players_sorted_with_status(db_session):
    import db as db_module
    import game_store

    game = game_store.get_active_game(db_session)
    game_store.upsert_player_state(
        db_session,
        game,
        uid="alpha",
        name="alice",
        state_data={"currentRow": 2, "gameOver": True, "isWinner": True},
    )
    game_store.upsert_player_state(
        db_session,
        game,
        uid="beta",
        name="Bob",
        state_data={"currentRow": 1, "gameOver": False, "isWinner": False},
    )

    players = db_module.list_players(db_session)

    assert [player["name"] for player in players] == ["alice", "Bob"]
    assert players[0]["tries"] == 3
    assert players[0]["status"] == "Success"
    assert players[1]["tries"] == 1
    assert players[1]["status"] == "Fail"
