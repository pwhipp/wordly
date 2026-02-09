# Wordly

A simple Wordle-style clone with a React frontend and a Flask backend.

## Requirements

- Node.js 18+
- Python 3.10+

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

The backend runs on `http://localhost:5000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`.

## Gameplay configuration

- The current game state (word, definition, scores, and players) lives in `backend/game_state.json`.
- Use the `/admin` page in the frontend to reset the game state and select a new word.

## Tests

```bash
cd backend
pytest
```
