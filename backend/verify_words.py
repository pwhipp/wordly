#!/usr/bin/env python3
import sys
import requests
import time


API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
TIMEOUT = 10
SLEEP_SECONDS = 2.1  # be polite to the API


def fetch_definition(word):
    try:
        response = requests.get(API_URL.format(word), timeout=TIMEOUT)
    except requests.RequestException as exc:
        return None, f"request error: {exc}"

    try:
        data = response.json()
    except ValueError:
        return None, f"http {response.status_code}: non-json response"

    if response.status_code != 200:
        # dictionaryapi.dev usually returns a structured error payload
        if isinstance(data, dict):
            title = data.get("title")
            message = data.get("message")
            resolution = data.get("resolution")

            reason = " | ".join(
                part for part in (title, message, resolution) if part
            )
            return None, reason or f"http {response.status_code}"
        else:
            return None, f"http {response.status_code}"

    # Successful HTTP response — now extract a definition
    try:
        meanings = data[0]["meanings"]
        for meaning in meanings:
            definitions = meaning.get("definitions", [])
            for definition in definitions:
                text = definition.get("definition")
                if text:
                    return text.strip(), None
    except (KeyError, IndexError, TypeError):
        return None, "unexpected response structure"

    return None, "no definition found"


def main(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = [line.rstrip("\n") for line in f if line.strip()]

    kept = []

    for line in lines:
        parts = line.split(" ", 1)
        if len(parts) != 2:
            raise Exception(f"Invalid line: {line}")

        word = parts[0]

        print(word, end=" ", flush=True)

        if len(word) != 5:
            print(f"deleted: length {len(word)}")
        else:
            definition, error = fetch_definition(word)
            if definition:
                print("ok")
                kept.append(f"{word} {definition}")
            else:
                print(f"deleted: {error}")

        time.sleep(SLEEP_SECONDS)

    with open(path, "w", encoding="utf-8") as f:
        for line in kept:
            f.write(line + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: verify_words.py <candidate_words.txt>")
        sys.exit(1)

    main(sys.argv[1])
