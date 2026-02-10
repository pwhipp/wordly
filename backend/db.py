from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

import game_store
from models import Base
from models import PlayerState

BASE_DIR = Path(__file__).resolve().parent
DB_CONFIG_FILE = BASE_DIR / "db_config.json"
DEFAULT_MAX_GUESSES = 6

_ENGINE = None
_SESSIONMAKER: Optional[sessionmaker] = None


def load_db_config() -> Dict[str, Any]:
    if not DB_CONFIG_FILE.exists():
        raise FileNotFoundError("db_config.json is missing.")
    return json.loads(DB_CONFIG_FILE.read_text(encoding="utf-8"))


def build_db_url() -> str:
    db_url = os.environ.get("WORDLY_DB_URL")
    if db_url:
        return db_url
    if DB_CONFIG_FILE.exists():
        config = load_db_config()
        return (
            f"{config['driver']}://{config['user']}:{config['password']}@"
            f"{config['host']}:{config['port']}/{config['database']}"
        )
    sqlite_path = BASE_DIR / "wordly.sqlite"
    return f"sqlite:///{sqlite_path}"


def configure_database(db_url: Optional[str] = None) -> None:
    global _ENGINE, _SESSIONMAKER
    if db_url is None:
        db_url = build_db_url()
    _ENGINE = create_engine(db_url, future=True, pool_pre_ping=True)
    _SESSIONMAKER = sessionmaker(bind=_ENGINE, expire_on_commit=False, future=True)
    Base.metadata.create_all(_ENGINE)


def rebuild_database(db_url: Optional[str] = None) -> None:
    if db_url is None:
        db_url = build_db_url()
    engine = create_engine(db_url, future=True, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def get_session() -> Session:
    if _SESSIONMAKER is None:
        configure_database()
    return _SESSIONMAKER()


def get_current_game_settings(session: Session) -> Dict[str, Any]:
    game = game_store.get_active_game(session)
    return {
        "gameUid": game.uid,
        "wordLength": game.word_length,
        "maxGuesses": game.max_guesses,
        "word": game.word,
        "definition": game.definition,
    }


def _normalize_tries(player_state: PlayerState) -> int:
    current_row = len(player_state.guesses)
    if not isinstance(current_row, int) or current_row < 0:
        current_row = 0
    return max(current_row, 0)


def list_players(session: Session) -> List[Dict[str, Any]]:
    game = game_store.get_active_game(session)
    players = session.scalars(
        select(PlayerState).where(PlayerState.game_id == game.id)
    ).all()
    results = []
    for player in players:
        tries = _normalize_tries(player)
        status = "Success" if player.is_winner is True else "Fail"
        results.append({"name": player.name, "tries": tries, "status": status})
    results.sort(key=lambda entry: entry["name"].casefold())
    return results


def _print_game_settings(session: Session) -> None:
    settings = get_current_game_settings(session)
    print(json.dumps(settings, indent=2, sort_keys=True))


def _print_players(session: Session) -> None:
    players = list_players(session)
    if not players:
        print("No players found.")
        return
    print("Name\tTries\tResult")
    for entry in players:
        print(f"{entry['name']}\t{entry['tries']}\t{entry['status']}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Database utilities.")
    parser.add_argument(
        "command",
        choices=["rebuild", "show", "players"],
        help="Command to execute.",
    )
    args = parser.parse_args()

    if args.command == "rebuild":
        rebuild_database()
        return

    with get_session() as session:
        if args.command == "show":
            _print_game_settings(session)
        elif args.command == "players":
            _print_players(session)


if __name__ == "__main__":
    main()
