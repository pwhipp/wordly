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

### Database (Postgres)

The backend expects a Postgres database. Copy the example config and update it with your
credentials (including an IANA timezone such as `Australia/Brisbane`):

```bash
cd backend
cp db_config.example.json db_config.json
```

Create the database and user (Ubuntu/Postgres defaults shown below):

```bash
sudo -u postgres psql <<'SQL'
CREATE USER wordly WITH PASSWORD 'change-me';
CREATE DATABASE wordly OWNER wordly;
GRANT ALL PRIVILEGES ON DATABASE wordly TO wordly;
SQL
```

To rebuild the database (drop and recreate all tables), run:

```bash
cd backend
python db.py rebuild
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173`.

## Gameplay configuration

- Game data (word, definition, scores, and player states) is stored in Postgres.
- Use the `/admin` page in the frontend to reset the game and select a new word.

## Tests

```bash
cd backend
pytest
```
