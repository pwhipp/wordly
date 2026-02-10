from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from flask import Flask, jsonify, request
from flask_cors import CORS

import db
import game_logic
import game_store

BASE_DIR = Path(__file__).resolve().parent
ADMIN_CODE_FILE = BASE_DIR / "admin_code.txt"

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
        "wordLength": active_game.word_length,
        "maxGuesses": active_game.max_guesses,
    }


def require_game_uid(payload: dict) -> str:
    raw_game_uid = payload.get("gameUid")
    if raw_game_uid is None:
        raise ValueError("gameUid is required")
    return game_logic.sanitize_text(raw_game_uid, "gameUid")


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
                "wordLength": game.word_length,
                "maxGuesses": game.max_guesses,
                "gameUid": game.uid,
                "git": get_git_metadata(),
            }
        )


@app.post("/api/guess")
def post_guess() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        guess = game_logic.sanitize_text(payload.get("guess"), "guess").upper()
        uid = game_logic.sanitize_text(payload.get("uid"), "uid")
        name = game_logic.sanitize_text(payload.get("name"), "name")
        game_uid = require_game_uid(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with db.get_session() as session:
        try:
            game = game_store.require_active_game(session, game_uid)
        except game_store.GameMismatchError as exc:
            return jsonify(build_game_mismatch_payload(exc.active_game)), 409

        if len(guess) != game.word_length:
            return jsonify({"error": "Invalid guess length."}), 400
        if not game_logic.is_valid_word(guess):
            return jsonify({"error": "That is not a word."}), 400

        try:
            state = game_store.apply_guess_for_player(
                session=session,
                game=game,
                uid=uid,
                name=name,
                guess=guess,
            )
        except game_store.PlayerStateConflictError as exc:
            return jsonify({"error": str(exc)}), 409
        except game_store.InvalidGuessSequenceError as exc:
            return jsonify({"error": str(exc)}), 400

        if state["isWinner"] and not game_store.score_exists(session, game, uid):
            finish_time = state.get("finishTime")
            start_time = state.get("startTime")
            if isinstance(finish_time, int) and isinstance(start_time, int):
                duration = max(1.0, (finish_time - start_time) / 1000)
            else:
                duration = 1.0
            tries = len(state.get("guesses", []))
            game_store.save_score(session, game, uid, name, max(tries, 1), duration)

        response = {"state": state}
        if state["gameOver"]:
            response["word"] = game.word
            response["definition"] = game.definition
        return jsonify(response)


@app.get("/api/scores")
def get_scores() -> Any:
    with db.get_session() as session:
        game = game_store.get_active_game(session)
        scores = game_store.sort_scores(game_store.load_scores(session, game))
        return jsonify([game_store.score_entry_to_dict(entry) for entry in scores])


@app.get("/api/state")
def get_state() -> Any:
    try:
        uid = game_logic.sanitize_text(request.args.get("uid"), "uid")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with db.get_session() as session:
        game = game_store.get_active_game(session)
        user_state = game_store.get_player_state(session, game, uid)
        return jsonify({"state": user_state})


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
