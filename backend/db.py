from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base

BASE_DIR = Path(__file__).resolve().parent
DB_CONFIG_FILE = BASE_DIR / "db_config.json"

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
    config = load_db_config()
    return (
        f"{config['driver']}://{config['user']}:{config['password']}@"
        f"{config['host']}:{config['port']}/{config['database']}"
    )


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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Database utilities.")
    parser.add_argument(
        "command",
        choices=["rebuild"],
        help="Command to execute.",
    )
    args = parser.parse_args()

    if args.command == "rebuild":
        rebuild_database()


if __name__ == "__main__":
    main()
