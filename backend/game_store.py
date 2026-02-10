from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from game_logic import choose_word_definition
from models import Game, PlayerGuess, PlayerKeyboardStatus, PlayerState, Score


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


class InvalidGuessSequenceError(ValueError):
    pass


def create_game(session: Session) -> Game:
    word, definition = choose_word_definition()
    game = Game(
        uid=uuid.uuid4().hex,
        word=word,
        definition=definition,
        max_guesses=6,
        word_length=len(word),
    )
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


def _serialize_player_state(record: PlayerState) -> dict[str, Any]:
    guesses = [
        {
            "guessNumber": guess.guess_number,
            "guess": guess.guess_text,
            "statuses": guess.statuses,
        }
        for guess in sorted(record.guesses, key=lambda item: item.guess_number)
    ]
    keyboard_statuses = {
        item.letter: item.status
        for item in sorted(record.keyboard_statuses, key=lambda status: status.letter)
    }
    current_row = len(guesses)
    return {
        "name": record.name,
        "isWinner": record.is_winner,
        "startTime": record.start_time,
        "finishTime": record.finish_time,
        "currentRow": current_row,
        "guesses": guesses,
        "keyboardStatuses": keyboard_statuses,
    }


def get_player_state(session: Session, game: Game, uid: str) -> Optional[dict]:
    record = session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.uid == uid,
        )
    )
    if record is None:
        return None
    return _serialize_player_state(record)


def get_player_state_record(
    session: Session, game: Game, uid: str
) -> Optional[PlayerState]:
    return session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.uid == uid,
        )
    )


def _validate_guess_sequence(guesses: list[dict[str, Any]], max_guesses: int) -> None:
    guess_numbers = sorted(guess["guessNumber"] for guess in guesses)
    if len(guess_numbers) > max_guesses:
        raise InvalidGuessSequenceError("Too many guesses for this game.")
    if guess_numbers and guess_numbers != list(range(1, len(guess_numbers) + 1)):
        raise InvalidGuessSequenceError(
            "Guesses must form a contiguous sequence starting at 1."
        )


def _replace_related_data(
    record: PlayerState,
    guesses: list[dict[str, Any]],
    keyboard_statuses: dict[str, str],
) -> None:
    record.guesses.clear()
    record.keyboard_statuses.clear()

    for guess in guesses:
        record.guesses.append(
            PlayerGuess(
                guess_number=guess["guessNumber"],
                guess_text=guess["guess"],
                statuses=guess["statuses"],
            )
        )

    for letter, status in keyboard_statuses.items():
        record.keyboard_statuses.append(
            PlayerKeyboardStatus(letter=letter, status=status)
        )


def upsert_player_state(
    session: Session,
    game: Game,
    uid: str,
    name: str,
    is_winner: bool,
    start_time: Optional[int],
    finish_time: Optional[int],
    guesses: list[dict[str, Any]],
    keyboard_statuses: dict[str, str],
) -> dict:
    _validate_guess_sequence(guesses, game.max_guesses)

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
            is_winner=is_winner,
            start_time=start_time,
            finish_time=finish_time,
        )
        session.add(record)
    else:
        record.name = name
        record.is_winner = is_winner
        record.start_time = start_time
        record.finish_time = finish_time

    existing_numbers = sorted(item.guess_number for item in record.guesses)
    incoming_numbers = sorted(item["guessNumber"] for item in guesses)
    if existing_numbers and incoming_numbers[: len(existing_numbers)] != existing_numbers:
        raise InvalidGuessSequenceError(
            "New guesses must extend the existing contiguous guess sequence."
        )

    _replace_related_data(record, guesses, keyboard_statuses)
    session.commit()
    return _serialize_player_state(record)


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
