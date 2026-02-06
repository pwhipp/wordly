import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = "http://localhost:5000/api";
const LETTER_STATUS = {
  correct: "correct",
  present: "present",
  absent: "absent"
};

const defaultKeyboard = [
  "QWERTYUIOP".split(""),
  "ASDFGHJKL".split(""),
  ["ENTER", ..."ZXCVBNM".split(""), "⌫"]
];

const statusPriority = {
  correct: 3,
  present: 2,
  absent: 1
};

const getStored = (key) => window.localStorage.getItem(key);
const setStored = (key, value) => window.localStorage.setItem(key, value);

const createEmptyGrid = (rows, cols) =>
  Array.from({ length: rows }, () =>
    Array.from({ length: cols }, () => ({ letter: "", status: "" }))
  );

const generateUid = () => {
  if (crypto?.randomUUID) {
    return crypto.randomUUID();
  }
  return `uid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export default function App() {
  const [wordLength, setWordLength] = useState(5);
  const [maxGuesses, setMaxGuesses] = useState(6);
  const [grid, setGrid] = useState(() => createEmptyGrid(6, 5));
  const [currentRow, setCurrentRow] = useState(0);
  const [currentCol, setCurrentCol] = useState(0);
  const [keyboardStatuses, setKeyboardStatuses] = useState({});
  const [message, setMessage] = useState("");
  const [gameOver, setGameOver] = useState(false);
  const [isWinner, setIsWinner] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showNamePrompt, setShowNamePrompt] = useState(false);
  const [playerName, setPlayerName] = useState("");
  const [scores, setScores] = useState([]);
  const [playerScore, setPlayerScore] = useState(null);
  const [startTime] = useState(Date.now());

  const scoreContainerRef = useRef(null);
  const playerScoreRef = useRef(null);

  const uid = useMemo(() => {
    let stored = getStored("wordly_uid");
    if (!stored) {
      stored = generateUid();
      setStored("wordly_uid", stored);
    }
    return stored;
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/config`)
      .then((res) => res.json())
      .then((data) => {
        setWordLength(data.wordLength);
        setMaxGuesses(data.maxGuesses);
        setGrid(createEmptyGrid(data.maxGuesses, data.wordLength));
      })
      .catch(() => setMessage("Unable to load game config."));
  }, []);

  useEffect(() => {
    const storedName = getStored("wordly_name");
    if (storedName) {
      setPlayerName(storedName);
    } else {
      setShowNamePrompt(true);
    }
    if (!getStored("wordly_help_seen")) {
      setShowHelp(true);
    }
  }, []);

  useEffect(() => {
    if (playerScoreRef.current && scoreContainerRef.current) {
      playerScoreRef.current.scrollIntoView({ block: "center" });
    }
  }, [scores]);

  const updateMessage = (text) => {
    setMessage(text);
    if (text) {
      setTimeout(() => setMessage(""), 2500);
    }
  };

  const applyKeyboardStatus = useCallback((letter, status) => {
    setKeyboardStatuses((prev) => {
      const current = prev[letter];
      if (!current || statusPriority[status] > statusPriority[current]) {
        return { ...prev, [letter]: status };
      }
      return prev;
    });
  }, []);

  const submitGuess = useCallback(
    async (guess) => {
      try {
        const response = await fetch(`${API_BASE}/guess`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ guess })
        });
        if (!response.ok) {
          const errorData = await response.json();
          updateMessage(errorData.error || "Guess rejected.");
          return;
        }
        const data = await response.json();
        setGrid((prev) => {
          const next = prev.map((row) => row.map((cell) => ({ ...cell })));
          data.statuses.forEach((status, index) => {
            next[currentRow][index] = {
              letter: guess[index],
              status
            };
          });
          return next;
        });
        data.statuses.forEach((status, index) =>
          applyKeyboardStatus(guess[index], status)
        );
        if (data.isCorrect) {
          setGameOver(true);
          setIsWinner(true);
          updateMessage("Genius!");
          await submitScore(currentRow + 1);
        } else if (currentRow + 1 >= maxGuesses) {
          setGameOver(true);
          updateMessage("Better luck next time.");
        } else {
          setCurrentRow((row) => row + 1);
          setCurrentCol(0);
        }
      } catch (error) {
        updateMessage("Could not submit guess.");
      }
    },
    [applyKeyboardStatus, currentRow, maxGuesses]
  );

  const submitScore = async (tries) => {
    try {
      const duration = Math.max(1, Math.round((Date.now() - startTime) / 1000));
      const response = await fetch(`${API_BASE}/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          uid,
          name: playerName,
          tries,
          duration
        })
      });
      if (!response.ok) {
        const errorData = await response.json();
        updateMessage(errorData.error || "Unable to submit score.");
        return;
      }
      const data = await response.json();
      setScores(data.scores || []);
      setPlayerScore(data.entry);
    } catch (error) {
      updateMessage("Unable to submit score.");
    }
  };

  const handleKeyPress = useCallback(
    (value) => {
      if (gameOver || showNamePrompt) {
        return;
      }
      const key = value.toUpperCase();
      if (key === "ENTER") {
        if (currentCol < wordLength) {
          updateMessage("Not enough letters");
          return;
        }
        const guess = grid[currentRow].map((cell) => cell.letter).join("");
        submitGuess(guess);
        return;
      }
      if (key === "⌫" || key === "BACKSPACE") {
        if (currentCol === 0) {
          return;
        }
        const targetCol = currentCol - 1;
        setGrid((prev) => {
          const next = prev.map((row) => row.map((cell) => ({ ...cell })));
          next[currentRow][targetCol].letter = "";
          next[currentRow][targetCol].status = "";
          return next;
        });
        setCurrentCol(targetCol);
        return;
      }
      if (/^[A-Z]$/.test(key)) {
        if (currentCol >= wordLength) {
          return;
        }
        setGrid((prev) => {
          const next = prev.map((row) => row.map((cell) => ({ ...cell })));
          next[currentRow][currentCol].letter = key;
          next[currentRow][currentCol].status = "";
          return next;
        });
        setCurrentCol((col) => col + 1);
      }
    },
    [currentCol, currentRow, gameOver, grid, showNamePrompt, submitGuess, wordLength]
  );

  useEffect(() => {
    const handleKeyDown = (event) => handleKeyPress(event.key);
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyPress]);

  const handleNameSubmit = (event) => {
    event.preventDefault();
    if (!playerName.trim()) {
      return;
    }
    const cleaned = playerName.trim();
    setPlayerName(cleaned);
    setStored("wordly_name", cleaned);
    setShowNamePrompt(false);
  };

  const closeHelp = () => {
    setStored("wordly_help_seen", "1");
    setShowHelp(false);
  };

  const scoreRows = scores.map((entry) => {
    const isPlayer = playerScore?.uid === entry.uid;
    return (
      <div
        key={entry.uid}
        className={`score-row ${isPlayer ? "highlight" : ""}`}
        ref={isPlayer ? playerScoreRef : null}
      >
        <span>{entry.name}</span>
        <span>{entry.tries} tries</span>
        <span>{entry.duration}s</span>
        <span>{entry.score}</span>
      </div>
    );
  });

  return (
    <div className="app">
      <header className="header">
        <h1>Wordly</h1>
        <button type="button" className="help-button" onClick={() => setShowHelp(true)}>
          ?
        </button>
      </header>
      {message && <div className="toast">{message}</div>}
      <section className="grid">
        {grid.map((row, rowIndex) => (
          <div
            key={`row-${rowIndex}`}
            className="row"
            style={{ gridTemplateColumns: `repeat(${wordLength}, 1fr)` }}
          >
            {row.map((cell, colIndex) => (
              <div
                key={`cell-${rowIndex}-${colIndex}`}
                className={`cell ${cell.status}`}
              >
                {cell.letter}
              </div>
            ))}
          </div>
        ))}
      </section>
      <section className="keyboard">
        {defaultKeyboard.map((row, rowIndex) => (
          <div key={`kbd-${rowIndex}`} className="keyboard-row">
            {row.map((key) => (
              <button
                key={key}
                type="button"
                className={`key ${keyboardStatuses[key] || ""}`}
                onClick={() => handleKeyPress(key)}
              >
                {key}
              </button>
            ))}
          </div>
        ))}
      </section>

      {showHelp && (
        <div className="modal">
          <div className="modal-content">
            <h2>How to play</h2>
            <p>Guess the Wordly in 6 tries.</p>
            <ul>
              <li>Each guess must be a valid 5-letter word.</li>
              <li>The color of the tiles will change to show how close your guess was.</li>
            </ul>
            <button type="button" onClick={closeHelp}>
              Got it
            </button>
          </div>
        </div>
      )}

      {showNamePrompt && (
        <div className="modal">
          <div className="modal-content">
            <h2>Welcome!</h2>
            <p>Enter your name to start playing.</p>
            <form onSubmit={handleNameSubmit}>
              <input
                type="text"
                value={playerName}
                onChange={(event) => setPlayerName(event.target.value)}
                placeholder="Your name"
                maxLength={20}
              />
              <button type="submit">Start</button>
            </form>
          </div>
        </div>
      )}

      {isWinner && (
        <div className="modal">
          <div className="modal-content scores">
            <h2>Hi Scores</h2>
            <div className="score-container" ref={scoreContainerRef}>
              {scoreRows.length ? scoreRows : <p>No scores yet.</p>}
            </div>
            <p className="score-note">
              Score equals total time taken (seconds) divided by the number of tries. Lower
              scores are better.
            </p>
            <button type="button" onClick={() => setIsWinner(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
