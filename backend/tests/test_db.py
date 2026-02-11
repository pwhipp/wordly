from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

import db as db_module  # noqa: E402
import models  # noqa: E402


def test_build_db_url_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("WORDLY_DB_URL", raising=False)
    monkeypatch.setattr(db_module, "DB_CONFIG_FILE", tmp_path / "db_config.json")
    monkeypatch.setattr(db_module, "BASE_DIR", tmp_path)

    assert db_module.build_db_url() == f"sqlite:///{tmp_path / 'wordly.sqlite'}"


def test_get_database_timezone_name_from_config(tmp_path, monkeypatch):
    config_file = tmp_path / "db_config.json"
    config_file.write_text(
        json.dumps({"timezone": "  Australia/Brisbane  "}),
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "DB_CONFIG_FILE", config_file)

    assert db_module.get_database_timezone_name() == "Australia/Brisbane"


def test_get_database_timezone_name_defaults_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_CONFIG_FILE", tmp_path / "db_config.json")

    assert db_module.get_database_timezone_name() == db_module.DEFAULT_DB_TIMEZONE


def test_configure_database_timezone_raises_for_invalid_value(tmp_path, monkeypatch):
    config_file = tmp_path / "db_config.json"
    config_file.write_text(
        json.dumps({"timezone": "Invalid/Timezone"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(db_module, "DB_CONFIG_FILE", config_file)

    with pytest.raises(ValueError, match="Invalid database timezone"):
        db_module.configure_database_timezone()


def test_get_current_db_time_uses_configured_timezone():
    models.set_db_timezone("Australia/Brisbane")

    current_time = models.get_current_db_time()

    assert current_time.tzinfo is not None
    assert getattr(current_time.tzinfo, "key", "") == "Australia/Brisbane"

    models.set_db_timezone("UTC")


def test_resolve_rebuild_word_definition_prefers_overrides(monkeypatch):
    monkeypatch.setattr(
        db_module,
        "choose_word_definition",
        lambda: ("CRATE", "A container."),
    )

    word, definition = db_module._resolve_rebuild_word_definition(
        word=" slate ",
        definition="  Custom clue.  ",
    )

    assert word == "SLATE"
    assert definition == "Custom clue."


def test_rebuild_database_seeds_overridden_word_and_definition(tmp_path):
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from models import Game

    db_path = tmp_path / "rebuild.sqlite"

    db_module.rebuild_database(
        db_url=f"sqlite:///{db_path}",
        word=" slate ",
        definition="  Custom clue.  ",
    )

    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with Session(engine) as session:
        games = session.scalars(select(Game)).all()

    assert len(games) == 1
    assert games[0].word == "SLATE"
    assert games[0].definition == "Custom clue."
