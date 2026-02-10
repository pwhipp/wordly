from __future__ import annotations

from datetime import datetime
from typing import List

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Game(Base):
    __tablename__ = "game"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    word: Mapped[str] = mapped_column(String(16), nullable=False)
    definition: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    max_guesses: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    word_length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    scores: Mapped[List["Score"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    player_states: Mapped[List["PlayerState"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class Score(Base):
    __tablename__ = "score"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    tries: Mapped[int] = mapped_column(Integer, nullable=False)
    duration: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[float] = mapped_column(Float, nullable=False)

    game: Mapped[Game] = relationship(back_populates="scores")


class PlayerState(Base):
    __tablename__ = "player_state"
    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_player_state_game_id_name"),
        UniqueConstraint("game_id", "uid", name="uq_player_state_game_id_uid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    uid: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_time: Mapped[int | None] = mapped_column(BigInteger)
    finish_time: Mapped[int | None] = mapped_column(BigInteger)

    game: Mapped[Game] = relationship(back_populates="player_states")
    guesses: Mapped[List["PlayerGuess"]] = relationship(
        back_populates="player_state", cascade="all, delete-orphan", order_by="PlayerGuess.guess_number"
    )
    keyboard_statuses: Mapped[List["PlayerKeyboardStatus"]] = relationship(
        back_populates="player_state", cascade="all, delete-orphan"
    )


class PlayerGuess(Base):
    __tablename__ = "player_guess"
    __table_args__ = (
        UniqueConstraint(
            "player_state_id", "guess_number", name="uq_player_guess_player_state_id_guess_number"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_state_id: Mapped[int] = mapped_column(ForeignKey("player_state.id"), nullable=False)
    guess_number: Mapped[int] = mapped_column(Integer, nullable=False)
    guess_text: Mapped[str] = mapped_column(String(16), nullable=False)
    statuses: Mapped[list[str]] = mapped_column(JSON, nullable=False)

    player_state: Mapped[PlayerState] = relationship(back_populates="guesses")


class PlayerKeyboardStatus(Base):
    __tablename__ = "player_keyboard_status"
    __table_args__ = (
        UniqueConstraint(
            "player_state_id", "letter", name="uq_player_keyboard_status_player_state_id_letter"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_state_id: Mapped[int] = mapped_column(ForeignKey("player_state.id"), nullable=False)
    letter: Mapped[str] = mapped_column(String(1), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    player_state: Mapped[PlayerState] = relationship(back_populates="keyboard_statuses")
