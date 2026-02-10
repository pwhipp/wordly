from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from game_logic import choose_word_definition, evaluate_guess
from models import Game, PlayerGuess, PlayerKeyboardStatus, PlayerState, Score

_STATUS_PRIORITY = {"absent": 1, "present": 2, "correct": 3}


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


class PlayerStateConflictError(ValueError):
    pass


def _now_millis() -> int:
    return int(time.time() * 1000)


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
    return sorted(
        scores,
        key=lambda entry: (entry.tries, entry.duration, entry.timestamp),
    )


def save_score(
    session: Session,
    game: Game,
    uid: str,
    name: str,
    tries: int,
    duration: float,
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


def _serialize_player_state(record: PlayerState, game: Game) -> dict[str, Any]:
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

    return {
        "name": record.name,
        "isWinner": record.is_winner,
        "startTime": record.start_time,
        "finishTime": record.finish_time,
        "currentRow": len(guesses),
        "currentCol": 0,
        "gameOver": record.finish_time is not None,
        "maxGuesses": game.max_guesses,
        "wordLength": game.word_length,
        "guesses": guesses,
        "keyboardStatuses": keyboard_statuses,
    }


def _validate_guess_sequence(guesses: list[PlayerGuess], max_guesses: int) -> None:
    guess_numbers = sorted(guess.guess_number for guess in guesses)
    if len(guess_numbers) > max_guesses:
        raise InvalidGuessSequenceError("Too many guesses for this game.")
    if guess_numbers and guess_numbers != list(range(1, len(guess_numbers) + 1)):
        raise InvalidGuessSequenceError(
            "Guesses must form a contiguous sequence starting at 1."
        )


def get_player_state(session: Session, game: Game, uid: str) -> Optional[dict]:
    record = get_player_state_record(session, game, uid)
    if record is None:
        return None
    return _serialize_player_state(record, game)


def get_player_state_record(
    session: Session,
    game: Game,
    uid: str,
) -> Optional[PlayerState]:
    return session.scalar(
        select(PlayerState).where(
            PlayerState.game_id == game.id,
            PlayerState.uid == uid,
        )
    )


def get_or_create_player_state(
    session: Session,
    game: Game,
    uid: str,
    name: str,
) -> PlayerState:
    record = get_player_state_record(session, game, uid)
    if record is not None:
        if record.name != name:
            if has_name_conflict(session, game, uid, name):
                raise PlayerStateConflictError(
                    f"The name {name} is already in use. Please choose another"
                )
            record.name = name
        return record

    if has_name_conflict(session, game, uid, name):
        raise PlayerStateConflictError(
            f"The name {name} is already in use. Please choose another"
        )

    record = PlayerState(
        game_id=game.id,
        uid=uid,
        name=name,
        is_winner=False,
        start_time=_now_millis(),
        finish_time=None,
    )
    session.add(record)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise PlayerStateConflictError(
            f"The name {name} is already in use. Please choose another"
        ) from exc
    return record


def _upsert_keyboard_statuses(
    record: PlayerState,
    guess: str,
    statuses: list[str],
) -> None:
    existing = {item.letter: item for item in record.keyboard_statuses}
    for letter, status in zip(guess, statuses):
        letter = letter.upper()
        new_rank = _STATUS_PRIORITY.get(status, 0)
        current = existing.get(letter)
        if current is None:
            item = PlayerKeyboardStatus(letter=letter, status=status)
            record.keyboard_statuses.append(item)
            existing[letter] = item
            continue
        current_rank = _STATUS_PRIORITY.get(current.status, 0)
        if new_rank > current_rank:
            current.status = status


def apply_guess_for_player(
    session: Session,
    game: Game,
    uid: str,
    name: str,
    guess: str,
) -> dict[str, Any]:
    record = get_or_create_player_state(session, game, uid, name)

    ordered_guesses = sorted(record.guesses, key=lambda item: item.guess_number)
    _validate_guess_sequence(ordered_guesses, game.max_guesses)

    if record.finish_time is not None:
        raise InvalidGuessSequenceError("Game is already over for this player.")

    next_guess_number = len(ordered_guesses) + 1
    if next_guess_number > game.max_guesses:
        raise InvalidGuessSequenceError("Maximum guesses reached for this game.")

    statuses = evaluate_guess(guess, game.word)
    record.guesses.append(
        PlayerGuess(
            guess_number=next_guess_number,
            guess_text=guess,
            statuses=statuses,
        )
    )
    _upsert_keyboard_statuses(record, guess, statuses)

    is_correct = guess == game.word
    if is_correct:
        record.is_winner = True
        record.finish_time = _now_millis()
    elif next_guess_number >= game.max_guesses:
        record.is_winner = False
        record.finish_time = _now_millis()

    session.commit()
    return _serialize_player_state(record, game)


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
