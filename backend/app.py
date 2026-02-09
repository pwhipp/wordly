from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from flask import Flask, jsonify, request
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
ADMIN_CODE_FILE = BASE_DIR / "admin_code.txt"
CANDIDATE_WORDS_FILE = BASE_DIR / "candidate_words.txt"
GAME_STATE_FILE = BASE_DIR / "game_state.json"
MAX_GUESSES = 6
STATE_LOCK = threading.RLock()

app = Flask(__name__)
CORS(app)


@dataclass
class ScoreEntry:
    uid: str
    name: str
    tries: int
    duration: float
    timestamp: float


def sanitize_word(raw_word: str) -> str:
    word = "".join(char for char in raw_word.strip().upper() if char.isalpha())
    if not word:
        raise ValueError("Word must contain alphabetic characters.")
    return word


def parse_candidate_line(line: str) -> Tuple[str, str]:
    parts = line.strip().split(" ", 1)
    if not parts or not parts[0]:
        raise ValueError("Invalid candidate word.")
    word = sanitize_word(parts[0])
    definition = parts[1].strip() if len(parts) > 1 else ""
    return word, definition


def choose_word_definition() -> Tuple[str, str]:
    if not CANDIDATE_WORDS_FILE.exists():
        return "CRATE", ""
    lines = [
        line
        for line in CANDIDATE_WORDS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    candidates = []
    for line in lines:
        try:
            candidates.append(parse_candidate_line(line))
        except ValueError:
            continue
    if not candidates:
        return "CRATE", ""
    return random.choice(candidates)


def build_new_game_state() -> Dict[str, Any]:
    word, definition = choose_word_definition()
    return {
        "gameUid": uuid.uuid4().hex,
        "word": word,
        "definition": definition,
        "scores": [],
        "players": {},
    }


def normalize_game_state(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return build_new_game_state()

    if not {"word", "definition", "scores", "players"} & data.keys():
        players = data if isinstance(data, dict) else {}
        word, definition = choose_word_definition()
        return {
            "gameUid": uuid.uuid4().hex,
            "word": word,
            "definition": definition,
            "scores": [],
            "players": players if isinstance(players, dict) else {},
        }

    players = data.get("players", {})
    scores = data.get("scores", [])
    word = data.get("word")
    definition = data.get("definition")
    game_uid = data.get("gameUid")

    if not isinstance(players, dict):
        players = {}
    if not isinstance(scores, list):
        scores = []

    if isinstance(word, str) and word.strip():
        try:
            word = sanitize_word(word)
        except ValueError:
            word = None
    else:
        word = None

    if word is None:
        word, definition = choose_word_definition()
    elif not isinstance(definition, str):
        definition = ""
    if not isinstance(game_uid, str) or not game_uid.strip():
        game_uid = uuid.uuid4().hex

    return {
        "gameUid": game_uid,
        "word": word,
        "definition": definition,
        "scores": scores,
        "players": players,
    }


def load_full_game_state() -> Dict[str, Any]:
    with STATE_LOCK:
        if not GAME_STATE_FILE.exists():
            state = build_new_game_state()
            save_game_state(state)
            return state
        try:
            data = json.loads(GAME_STATE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        state = normalize_game_state(data)
        if state != data:
            save_game_state(state)
        return state


def load_word() -> str:
    state = load_full_game_state()
    return state["word"]


def load_scores() -> List[ScoreEntry]:
    state = load_full_game_state()
    scores = []
    for entry in state.get("scores", []):
        if not isinstance(entry, dict):
            continue
        entry_data = dict(entry)
        entry_data.pop("score", None)
        try:
            scores.append(ScoreEntry(**entry_data))
        except TypeError:
            continue
    return scores


def save_scores(scores: List[ScoreEntry]) -> None:
    with STATE_LOCK:
        state = load_full_game_state()
        state["scores"] = [asdict(entry) for entry in scores]
        save_game_state(state)


def sort_scores(scores: List[ScoreEntry]) -> List[ScoreEntry]:
    return sorted(scores, key=lambda entry: (entry.tries, entry.duration, entry.timestamp))


def evaluate_guess(guess: str, word: str) -> List[str]:
    statuses = ["absent"] * len(word)
    remaining: Dict[str, int] = {}

    for index, (g_char, w_char) in enumerate(zip(guess, word)):
        if g_char == w_char:
            statuses[index] = "correct"
        else:
            remaining[w_char] = remaining.get(w_char, 0) + 1

    for index, (g_char, w_char) in enumerate(zip(guess, word)):
        if g_char == w_char:
            continue
        if remaining.get(g_char, 0) > 0:
            statuses[index] = "present"
            remaining[g_char] -= 1

    return statuses


def sanitize_text(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


def sanitize_int(value: Any, field: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def sanitize_float(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def sanitize_state_payload(state: Any) -> Dict[str, Any]:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    sanitized: Dict[str, Any] = {}
    if "grid" in state:
        if not isinstance(state["grid"], list):
            raise ValueError("grid must be a list")
        sanitized["grid"] = state["grid"]
    if "currentRow" in state:
        sanitized["currentRow"] = sanitize_int(state["currentRow"], "currentRow")
    if "currentCol" in state:
        sanitized["currentCol"] = sanitize_int(state["currentCol"], "currentCol")
    if "keyboardStatuses" in state:
        if not isinstance(state["keyboardStatuses"], dict):
            raise ValueError("keyboardStatuses must be an object")
        sanitized["keyboardStatuses"] = state["keyboardStatuses"]
    if "gameOver" in state:
        if not isinstance(state["gameOver"], bool):
            raise ValueError("gameOver must be a boolean")
        sanitized["gameOver"] = state["gameOver"]
    if "isWinner" in state:
        if not isinstance(state["isWinner"], bool):
            raise ValueError("isWinner must be a boolean")
        sanitized["isWinner"] = state["isWinner"]
    if "startTime" in state:
        sanitized["startTime"] = sanitize_int(state["startTime"], "startTime")
    if "maxGuesses" in state:
        sanitized["maxGuesses"] = sanitize_int(state["maxGuesses"], "maxGuesses")
    if "wordLength" in state:
        sanitized["wordLength"] = sanitize_int(state["wordLength"], "wordLength")
    return sanitized


def load_players() -> Dict[str, Dict[str, Any]]:
    state = load_full_game_state()
    players = state.get("players", {})
    return players if isinstance(players, dict) else {}


def save_game_state(state: Dict[str, Any]) -> None:
    with STATE_LOCK:
        GAME_STATE_FILE.write_text(json.dumps(state, indent=4), encoding="utf-8")


def save_players(players: Dict[str, Dict[str, Any]]) -> None:
    with STATE_LOCK:
        state = load_full_game_state()
        state["players"] = players
        save_game_state(state)


def load_admin_code() -> str:
    if not ADMIN_CODE_FILE.exists():
        raise FileNotFoundError("admin_code.txt is missing.")
    return ADMIN_CODE_FILE.read_text(encoding="utf-8").strip()


def build_user_state(name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    user_state = {"name": name}
    user_state.update({key: value for key, value in state.items() if key != "name"})
    return user_state


def is_valid_word(guess: str) -> bool:
    safe_guess = urllib.parse.quote(guess.lower())
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{safe_guess}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "wordly/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.status == 200
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False
        return True
    except (urllib.error.URLError, TimeoutError, ValueError):
        return True


@app.get("/api/config")
def get_config() -> Any:
    state = load_full_game_state()
    return jsonify(
        {
            "wordLength": len(state["word"]),
            "maxGuesses": MAX_GUESSES,
            "gameUid": state["gameUid"],
        }
    )


@app.post("/api/guess")
def post_guess() -> Any:
    payload = request.get_json(silent=True) or {}
    guess = sanitize_text(payload.get("guess"), "guess").upper()
    word = load_word()
    if len(guess) != len(word):
        return jsonify({"error": "Invalid guess length."}), 400
    if not is_valid_word(guess):
        return jsonify({"error": "That is not a word."}), 400
    statuses = evaluate_guess(guess, word)
    return jsonify({"statuses": statuses, "guess": guess, "isCorrect": guess == word})


@app.get("/api/scores")
def get_scores() -> Any:
    scores = sort_scores(load_scores())
    return jsonify([asdict(entry) for entry in scores])


@app.post("/api/submit")
def post_submit() -> Any:
    payload = request.get_json(silent=True) or {}
    try:
        uid = sanitize_text(payload.get("uid"), "uid")
        name = sanitize_text(payload.get("name"), "name")
        tries = sanitize_int(payload.get("tries"), "tries")
        duration = sanitize_float(payload.get("duration"), "duration")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if tries <= 0:
        return jsonify({"error": "tries must be positive."}), 400
    if duration <= 0:
        return jsonify({"error": "duration must be positive."}), 400

    scores = load_scores()
    if any(entry.uid == uid for entry in scores):
        return jsonify({"error": "Score already submitted for this device."}), 409

    entry = ScoreEntry(
        uid=uid,
        name=name,
        tries=tries,
        duration=duration,
        timestamp=time.time(),
    )
    scores.append(entry)
    scores = sort_scores(scores)
    save_scores(scores)

    return jsonify(
        {
            "entry": asdict(entry),
            "scores": [asdict(item) for item in scores],
        }
    )


@app.get("/api/state")
def get_state() -> Any:
    uid = sanitize_text(request.args.get("uid"), "uid")
    players = load_players()
    user_state = players.get(uid)
    return jsonify({"state": user_state})


@app.post("/api/state")
def post_state() -> Any:
    payload = request.get_json(silent=True) or {}
    uid = sanitize_text(payload.get("uid"), "uid")
    name = sanitize_text(payload.get("name"), "name")
    try:
        sanitized_state = sanitize_state_payload(payload.get("state", {}))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    players = load_players()
    for existing_uid, existing_state in players.items():
        if existing_uid != uid and existing_state.get("name") == name:
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

    players[uid] = build_user_state(name, sanitized_state)
    save_players(players)
    return jsonify({"state": players[uid]})


@app.post("/api/admin/verify")
def post_admin_verify() -> Any:
    payload = request.get_json(silent=True) or {}
    code = sanitize_text(payload.get("code"), "code")
    try:
        admin_code = load_admin_code()
    except FileNotFoundError:
        return jsonify({"error": "Admin code unavailable."}), 500
    return jsonify({"valid": code == admin_code})


@app.post("/api/admin/reset")
def post_admin_reset() -> Any:
    payload = request.get_json(silent=True) or {}
    code = sanitize_text(payload.get("code"), "code")
    try:
        admin_code = load_admin_code()
    except FileNotFoundError:
        return jsonify({"error": "Admin code unavailable."}), 500
    if code != admin_code:
        return jsonify({"error": "Invalid admin code."}), 403

    state = build_new_game_state()
    save_game_state(state)
    return jsonify({"word": state["word"], "definition": state["definition"]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
