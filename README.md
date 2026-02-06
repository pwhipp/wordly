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

- Update the daily word by editing `backend/words.txt`.
- Clear the hi score table by deleting `backend/scores.json` (it will be recreated on the next submission).

## Tests

```bash
cd backend
pytest
```
