from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, request
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
WORD_FILE = BASE_DIR / "words.txt"
SCORES_FILE = BASE_DIR / "scores.json"
GAME_STATE_FILE = BASE_DIR / "game_state.json"
MAX_GUESSES = 6

app = Flask(__name__)
CORS(app)


@dataclass
class ScoreEntry:
    uid: str
    name: str
    score: float
    tries: int
    duration: float
    timestamp: float


def sanitize_word(raw_word: str) -> str:
    word = "".join(char for char in raw_word.strip().upper() if char.isalpha())
    if not word:
        raise ValueError("Word must contain alphabetic characters.")
    return word


def load_word() -> str:
    if not WORD_FILE.exists():
        raise FileNotFoundError("words.txt is missing.")
    raw = WORD_FILE.read_text(encoding="utf-8").strip()
    return sanitize_word(raw)


def load_scores() -> List[ScoreEntry]:
    if not SCORES_FILE.exists():
        return []
    data = json.loads(SCORES_FILE.read_text(encoding="utf-8"))
    scores = []
    for entry in data:
        scores.append(ScoreEntry(**entry))
    return scores


def save_scores(scores: List[ScoreEntry]) -> None:
    data = [asdict(entry) for entry in scores]
    SCORES_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def sort_scores(scores: List[ScoreEntry]) -> List[ScoreEntry]:
    return sorted(scores, key=lambda entry: entry.score)


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


def load_game_state() -> Dict[str, Dict[str, Any]]:
    if not GAME_STATE_FILE.exists():
        return {}
    data = json.loads(GAME_STATE_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    return data


def save_game_state(state: Dict[str, Dict[str, Any]]) -> None:
    GAME_STATE_FILE.write_text(json.dumps(state, indent=4), encoding="utf-8")


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
    word = load_word()
    return jsonify({"wordLength": len(word), "maxGuesses": MAX_GUESSES})


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
    uid = sanitize_text(payload.get("uid"), "uid")
    name = sanitize_text(payload.get("name"), "name")
    tries = sanitize_int(payload.get("tries"), "tries")
    duration = sanitize_float(payload.get("duration"), "duration")

    if tries <= 0:
        return jsonify({"error": "tries must be positive."}), 400
    if duration <= 0:
        return jsonify({"error": "duration must be positive."}), 400

    scores = load_scores()
    if any(entry.uid == uid for entry in scores):
        return jsonify({"error": "Score already submitted for this device."}), 409

    score_value = round(duration / tries, 2)
    entry = ScoreEntry(
        uid=uid,
        name=name,
        score=score_value,
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
    state = load_game_state()
    user_state = state.get(uid)
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

    state = load_game_state()
    for existing_uid, existing_state in state.items():
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

    state[uid] = build_user_state(name, sanitized_state)
    save_game_state(state)
    return jsonify({"state": state[uid]})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
