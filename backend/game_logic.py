from __future__ import annotations

import random
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

BASE_DIR = Path(__file__).resolve().parent
CANDIDATE_WORDS_FILE = BASE_DIR / "candidate_words.txt"


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


def evaluate_guess(guess: str, word: str) -> list[str]:
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
