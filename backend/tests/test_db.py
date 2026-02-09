from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

import db as db_module  # noqa: E402


def test_build_db_url_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("WORDLY_DB_URL", raising=False)
    monkeypatch.setattr(db_module, "DB_CONFIG_FILE", tmp_path / "db_config.json")
    monkeypatch.setattr(db_module, "BASE_DIR", tmp_path)

    assert (
        db_module.build_db_url()
        == f"sqlite:///{tmp_path / 'wordly.sqlite'}"
    )
