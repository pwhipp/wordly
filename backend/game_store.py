from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from game_logic import build_user_state, choose_word_definition
from models import Game, PlayerState, Score


@dataclass
class ScoreEntry:
    uid: str
    name: str
    tries: int
    duration: float
    timestamp: float


class GameMismatchError(RuntimeError):
    def __init__(self, active_game: Game) -> None:
        super().__init__("Game has reset. Please start a new game.")
        self.active_game = active_game


def create_game(session: Session) -> Game:
    word, definition = choose_word_definition()
    game = Game(uid=uuid.uuid4().hex, word=word, definition=definition)
    session.add(game)
    session.commit()
    return game


def get_active_game(session: Session) -> Game:
    game = session.scalar(select(Game).order_by(Game.created_at.desc()))
    if game is None:
        game = create_game(session)
    return game


def require_active_game(session: Session, game_uid: str) -> Game:
    active_game = get_active_game(session)
    if game_uid != active_game.uid:
        raise GameMismatchError(active_game)
    return active_game


def load_scores(session: Session, game: Game) -> List[ScoreEntry]:
    entries = session.scalars(select(Score).where(Score.game_id == game.id)).all()
    return [
        ScoreEntry(
            uid=entry.uid,
            name=entry.name,
            tries=entry.tries,
            duration=entry.duration,
            timestamp=entry.timestamp,
        )
        for entry in entries
    ]


def sort_scores(scores: List[ScoreEntry]) -> List[ScoreEntry]:
    return sorted(scores, key=lambda entry: (entry.tries, entry.duration, entry.timestamp))


def save_score(
    session: Session, game: Game, uid: str, name: str, tries: int, duration: float
) -> ScoreEntry:
    score = Score(
        game_id=game.id,
        uid=uid,
        name=name,
        tries=tries,
        duration=duration,
        timestamp=time.time(),
    )
    session.add(score)
    session.commit()
    return ScoreEntry(
        uid=score.uid,
        name=score.name,
        tries=score.tries,
        duration=score.duration,
        timestamp=score.timestamp,
    )


def get_player_state(session: Session, game: Game, uid: str) -> Optional[dict]:
    record = session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.uid == uid,
        )
    )
    if record is None:
        return None
    return build_user_state(record.name, record.state_data)


def upsert_player_state(
    session: Session, game: Game, uid: str, name: str, state_data: dict
) -> dict:
    record = session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.uid == uid,
        )
    )
    if record is None:
        record = PlayerState(
            game_id=game.id,
            uid=uid,
            name=name,
            state_data=state_data,
        )
        session.add(record)
    else:
        record.name = name
        record.state_data = state_data
    session.commit()
    return build_user_state(record.name, record.state_data)


def has_name_conflict(session: Session, game: Game, uid: str, name: str) -> bool:
    conflict = session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.name == name,
            PlayerState.uid != uid,
        )
    )
    return conflict is not None


def score_exists(session: Session, game: Game, uid: str) -> bool:
    existing = session.scalar(
        select(Score).where(Score.game_id == game.id, Score.uid == uid)
    )
    return existing is not None


def score_entry_to_dict(entry: ScoreEntry) -> dict:
    return asdict(entry)
