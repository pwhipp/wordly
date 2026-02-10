from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS

import db
import game_logic
import game_store

BASE_DIR = Path(__file__).resolve().parent
ADMIN_CODE_FILE = BASE_DIR / "admin_code.txt"
MAX_GUESSES = 6

app = Flask(__name__)
CORS(app)


def load_admin_code() -> str:
    if not ADMIN_CODE_FILE.exists():
        raise FileNotFoundError("admin_code.txt is missing.")
    return ADMIN_CODE_FILE.read_text(encoding="utf-8").strip()


def build_game_mismatch_payload(active_game: Any) -> dict:
    return {
        "error": "Game has reset. Please start a new game.",
        "nextGameUid": active_game.uid,
        "wordLength": len(active_game.word),
        "maxGuesses": MAX_GUESSES,
    }


def require_game_uid(payload: dict) -> str:
    raw_game_uid = payload.get("gameUid")
    if raw_game_uid is None:
        raise ValueError("gameUid is required")
    return game_logic.sanitize_text(raw_game_uid, "gameUid")


def optional_text(payload: dict, field: str) -> Optional[str]:
    raw_value = payload.get(field)
    if raw_value is None:
        return None
    return game_logic.sanitize_text(raw_value, field)


def compute_score_from_state(state: dict) -> Tuple[int, float]:
    current_row = state.get("currentRow", 0)
    if not isinstance(current_row, int) or current_row < 0:
        current_row = 0
    tries = current_row + 1
    start_time = state.get("startTime")
    now = time.time()
    if isinstance(start_time, int):
        if start_time > 10_000_000_000:
            duration = max(1.0, (now * 1000 - start_time) / 1000)
        else:
            duration = max(1.0, now - start_time)
    else:
        duration = 1.0
    return tries, duration


def run_git_command(args: list[str]) -> Optional[str]:
    repo_root = BASE_DIR.parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=1,
        )
    except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    if not value:
        return None
    return value


def get_git_metadata() -> dict[str, Optional[str]]:
    return {
        "branch": run_git_command(["rev-parse", "--abbrev-ref", "HEAD"]),
        "head": run_git_command(["rev-parse", "HEAD"]),
    }


@app.get("/api/config")
def get_config() -> Any:
    with db.get_session() as session:
        game = game_store.get_active_game(session)
        return jsonify(
            {
                "wordLength": len(game.word),
                "maxGuesses": MAX_GUESSES,
                "gameUid": game.uid,
                "git": get_git_metadata(),
            }
        )


@app.post("/api/guess")
def post_guess() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        guess = game_logic.sanitize_text(payload.get("guess"), "guess").upper()
        game_uid = require_game_uid(payload)
        uid = optional_text(payload, "uid")
        name = optional_text(payload, "name")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    with db.get_session() as session:
        try:
            game = game_store.require_active_game(session, game_uid)
        except game_store.GameMismatchError as exc:
            return jsonify(build_game_mismatch_payload(exc.active_game)), 409
        word = game.word
    if len(guess) != len(word):
        return jsonify({"error": "Invalid guess length."}), 400
    if not game_logic.is_valid_word(guess):
        return jsonify({"error": "That is not a word."}), 400
    statuses = game_logic.evaluate_guess(guess, word)
    is_correct = guess == word
    if is_correct and uid:
        with db.get_session() as session:
            game = game_store.require_active_game(session, game_uid)
            if not game_store.score_exists(session, game, uid):
                player_record = game_store.get_player_state_record(
                    session, game, uid
                )
                if player_record:
                    tries, duration = compute_score_from_state(
                        player_record.state_data or {}
                    )
                    player_name = player_record.name
                elif name:
                    tries, duration = 1, 1.0
                    player_name = name
                else:
                    player_name = None
                if player_name:
                    game_store.save_score(
                        session, game, uid, player_name, tries, duration
                    )
    response = {"statuses": statuses, "guess": guess, "isCorrect": is_correct}
    if is_correct:
        response["word"] = game.word
        response["definition"] = game.definition
    return jsonify(response)


@app.get("/api/scores")
def get_scores() -> Any:
    with db.get_session() as session:
        game = game_store.get_active_game(session)
        scores = game_store.sort_scores(game_store.load_scores(session, game))
        return jsonify([game_store.score_entry_to_dict(entry) for entry in scores])


@app.post("/api/submit")
def post_submit() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        uid = game_logic.sanitize_text(payload.get("uid"), "uid")
        name = game_logic.sanitize_text(payload.get("name"), "name")
        tries = game_logic.sanitize_int(payload.get("tries"), "tries")
        duration = game_logic.sanitize_float(payload.get("duration"), "duration")
        game_uid = require_game_uid(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if tries <= 0:
        return jsonify({"error": "tries must be positive."}), 400
    if duration <= 0:
        return jsonify({"error": "duration must be positive."}), 400

    with db.get_session() as session:
        try:
            game = game_store.require_active_game(session, game_uid)
        except game_store.GameMismatchError as exc:
            return jsonify(build_game_mismatch_payload(exc.active_game)), 409
        if game_store.score_exists(session, game, uid):
            return jsonify({"error": "Score already submitted for this device."}), 409
        entry = game_store.save_score(session, game, uid, name, tries, duration)
        scores = game_store.sort_scores(game_store.load_scores(session, game))

    return jsonify(
        {
            "entry": game_store.score_entry_to_dict(entry),
            "scores": [game_store.score_entry_to_dict(item) for item in scores],
            "word": game.word,
            "definition": game.definition,
        }
    )


@app.get("/api/state")
def get_state() -> Any:
    uid = game_logic.sanitize_text(request.args.get("uid"), "uid")
    with db.get_session() as session:
        game = game_store.get_active_game(session)
        user_state = game_store.get_player_state(session, game, uid)
        return jsonify({"state": user_state})


@app.post("/api/state")
def post_state() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        uid = game_logic.sanitize_text(payload.get("uid"), "uid")
        name = game_logic.sanitize_text(payload.get("name"), "name")
        game_uid = require_game_uid(payload)
        sanitized_state = game_logic.sanitize_state_payload(payload.get("state", {}))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with db.get_session() as session:
        try:
            game = game_store.require_active_game(session, game_uid)
        except game_store.GameMismatchError as exc:
            return jsonify(build_game_mismatch_payload(exc.active_game)), 409
        if game_store.has_name_conflict(session, game, uid, name):
            return (
                jsonify(
                    {
                        "error": (
                            f"The name {name} is already in use. Please choose another"
                        )
                    }
                ),
                409,
            )
        state = game_store.upsert_player_state(
            session, game, uid, name, sanitized_state
        )
        return jsonify({"state": state})


@app.post("/api/admin/verify")
def post_admin_verify() -> Any:
    payload = request.get_json(silent=True) or {}
    code = game_logic.sanitize_text(payload.get("code"), "code")
    try:
        admin_code = load_admin_code()
    except FileNotFoundError:
        return jsonify({"error": "Admin code unavailable."}), 500
    return jsonify({"valid": code == admin_code})


@app.post("/api/admin/reset")
def post_admin_reset() -> Any:
    payload = request.get_json(silent=True) or {}
    code = game_logic.sanitize_text(payload.get("code"), "code")
    try:
        admin_code = load_admin_code()
    except FileNotFoundError:
        return jsonify({"error": "Admin code unavailable."}), 500
    if code != admin_code:
        return jsonify({"error": "Invalid admin code."}), 403
    with db.get_session() as session:
        game = game_store.create_game(session)
        return jsonify({"word": game.word, "definition": game.definition})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
