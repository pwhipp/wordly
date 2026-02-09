import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.DEV ? "http://localhost:5000/api" : "/api");
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
const removeStored = (key) => window.localStorage.removeItem(key);

const gameUidStorageKey = () => "wordly_game_uid";

const clearStoredGameState = () => {
  removeStored(gameUidStorageKey());
  removeStored("wordly_help_seen");
};

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

const AdminPanel = () => {
  const [adminCode, setAdminCode] = useState("");
  const [codeValid, setCodeValid] = useState(false);
  const [showCode, setShowCode] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [showConfirm, setShowConfirm] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);

  useEffect(() => {
    if (!adminCode) {
      setCodeValid(false);
      setStatusMessage("");
      return;
    }
    setIsVerifying(true);
    const handle = setTimeout(async () => {
      try {
        const response = await fetch(`${API_BASE}/admin/verify`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: adminCode })
        });
        if (!response.ok) {
          throw new Error("verify");
        }
        const data = await response.json();
        setCodeValid(Boolean(data.valid));
        setStatusMessage(data.valid ? "" : "Admin code is incorrect.");
      } catch (error) {
        setCodeValid(false);
        setStatusMessage("Unable to verify admin code.");
      } finally {
        setIsVerifying(false);
      }
    }, 300);
    return () => clearTimeout(handle);
  }, [adminCode]);

  const performReset = async () => {
    setIsResetting(true);
    setStatusMessage("");
    try {
      const response = await fetch(`${API_BASE}/admin/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: adminCode })
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Reset failed.");
      }
      setStatusMessage("Game state reset successfully.");
    } catch (error) {
      setStatusMessage(error.message || "Unable to reset game.");
    } finally {
      setIsResetting(false);
      setShowConfirm(false);
    }
  };

  const handleResetClick = async () => {
    if (!codeValid || isResetting) {
      return;
    }
    setStatusMessage("");
    try {
      const response = await fetch(`${API_BASE}/scores`);
      if (!response.ok) {
        throw new Error("scores");
      }
      const data = await response.json();
      if (data.length === 0) {
        setShowConfirm(true);
        return;
      }
      await performReset();
    } catch (error) {
      setStatusMessage("Unable to check scores before reset.");
    }
  };

  return (
    <div className="app admin-app">
      <header className="header">
        <h1>Admin Control</h1>
      </header>
      <section className="admin-panel">
        <label htmlFor="admin-code" className="admin-label">
          admin code:
        </label>
        <div className="admin-code-field">
          <input
            id="admin-code"
            type={showCode ? "text" : "password"}
            value={adminCode}
            onChange={(event) => setAdminCode(event.target.value)}
            placeholder="Enter admin code"
          />
          <button
            type="button"
            className="toggle-visibility"
            onClick={() => setShowCode((prev) => !prev)}
            aria-label={showCode ? "Hide admin code" : "Show admin code"}
          >
            {showCode ? "🙈" : "👁"}
          </button>
        </div>
        {statusMessage && <p className="admin-status">{statusMessage}</p>}
        <button
          type="button"
          className="admin-reset"
          onClick={handleResetClick}
          disabled={!codeValid || isResetting || isVerifying}
        >
          Reset (clears the game state, scores and sets a new word)
        </button>
      </section>

      {showConfirm && (
        <div className="modal">
          <div className="modal-content">
            <h2>Confirm reset</h2>
            <p>
              Nobody has completed this puzzle yet. Are you sure you want to reset it?
            </p>
            <div className="confirm-actions">
              <button type="button" onClick={performReset}>
                Yes
              </button>
              <button type="button" onClick={() => setShowConfirm(false)}>
                No
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const GameApp = () => {
  const [wordLength, setWordLength] = useState(5);
  const [maxGuesses, setMaxGuesses] = useState(6);
  const [grid, setGrid] = useState(() => createEmptyGrid(6, 5));
  const [currentRow, setCurrentRow] = useState(0);
  const [currentCol, setCurrentCol] = useState(0);
  const [keyboardStatuses, setKeyboardStatuses] = useState({});
  const [message, setMessage] = useState("");
  const [invalidGuessActive, setInvalidGuessActive] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [isWinner, setIsWinner] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showNamePrompt, setShowNamePrompt] = useState(false);
  const [playerName, setPlayerName] = useState("");
  const [pendingName, setPendingName] = useState("");
  const [nameError, setNameError] = useState("");
  const [scores, setScores] = useState([]);
  const [playerScore, setPlayerScore] = useState(null);
  const [solutionWord, setSolutionWord] = useState("");
  const [solutionDefinition, setSolutionDefinition] = useState("");
  const [startTime, setStartTime] = useState(Date.now());
  const [configLoaded, setConfigLoaded] = useState(false);
  const [gameUid, setGameUid] = useState(null);
  const [showScoresOverlay, setShowScoresOverlay] = useState(false);

  const scoreContainerRef = useRef(null);
  const playerScoreRef = useRef(null);
  const messageTimeoutRef = useRef(null);
  const hasLoadedStateRef = useRef(false);

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
        const nextGameUid = data.gameUid || null;
        setWordLength(data.wordLength);
        setMaxGuesses(data.maxGuesses);
        setGrid(createEmptyGrid(data.maxGuesses, data.wordLength));
        setGameUid(nextGameUid);
        if (nextGameUid) {
          setStored(gameUidStorageKey(), nextGameUid);
        }
        setConfigLoaded(true);
      })
      .catch(() => setMessage("Unable to load game config."));
  }, [uid]);

  useEffect(() => {
    if (!getStored("wordly_help_seen")) {
      setShowHelp(true);
    }
  }, []);

  const updateMessage = useCallback((text, { autoClear = true } = {}) => {
    if (messageTimeoutRef.current) {
      clearTimeout(messageTimeoutRef.current);
      messageTimeoutRef.current = null;
    }
    setMessage(text);
    if (text && autoClear) {
      messageTimeoutRef.current = setTimeout(() => {
        setMessage("");
        messageTimeoutRef.current = null;
      }, 2500);
    }
  }, []);

  const resolveActiveGameUid = useCallback(
    async (currentGameUid) => {
      const storedGameUid = getStored(gameUidStorageKey());
      const fallbackGameUid = currentGameUid || storedGameUid;
      try {
        const response = await fetch(`${API_BASE}/config`);
        if (!response.ok) {
          throw new Error("config");
        }
        const configData = await response.json();
        if (configData.gameUid && configData.gameUid !== fallbackGameUid) {
          setGameUid(configData.gameUid);
          setStored(gameUidStorageKey(), configData.gameUid);
        }
        return configData.gameUid || fallbackGameUid;
      } catch (error) {
        return fallbackGameUid || null;
      }
    },
    [setGameUid]
  );

  const loadScores = useCallback(async () => {
    try {
      const scoresResponse = await fetch(`${API_BASE}/scores`);
      if (!scoresResponse.ok) {
        throw new Error("scores");
      }
      const scoreData = await scoresResponse.json();
      setScores(scoreData);
      const matchingScore = scoreData.find((entry) => entry.uid === uid);
      setPlayerScore(matchingScore || null);
    } catch (scoresError) {
      updateMessage("Unable to load scores.");
    }
  }, [uid, updateMessage]);

  useEffect(() => {
    if (!configLoaded || hasLoadedStateRef.current) {
      return;
    }
    const fetchState = async () => {
      try {
        const response = await fetch(
          `${API_BASE}/state?uid=${encodeURIComponent(uid)}`
        );
        if (!response.ok) {
          throw new Error("state");
        }
        const data = await response.json();
        if (data.state) {
          const state = data.state;
          if (gameUid) {
            setStored(gameUidStorageKey(), gameUid);
          }
          setWordLength(state.wordLength || wordLength);
          setMaxGuesses(state.maxGuesses || maxGuesses);
          setGrid(
            state.grid || createEmptyGrid(maxGuesses, wordLength)
          );
          setCurrentRow(state.currentRow ?? 0);
          setCurrentCol(state.currentCol ?? 0);
          setKeyboardStatuses(state.keyboardStatuses || {});
          setGameOver(state.gameOver || false);
          setIsWinner(state.isWinner || false);
          setShowScoresOverlay(state.isWinner || false);
          if (state.isWinner) {
            setShowHelp(false);
            setStored("wordly_help_seen", "1");
          }
          setStartTime(state.startTime || Date.now());
          setPlayerName(state.name || "");
          setPendingName(state.name || "");
          setNameError("");
          if (state.name) {
            setStored("wordly_name", state.name);
            setShowNamePrompt(false);
          } else {
            setShowNamePrompt(true);
          }
          if (state.isWinner) {
            await loadScores();
          }
        } else {
          const storedName = getStored("wordly_name");
          if (storedName) {
            const activeGameUid = await resolveActiveGameUid(gameUid);
            if (!activeGameUid) {
              updateMessage("Unable to connect to the game server.");
              setPendingName(storedName);
              setNameError("");
              setShowNamePrompt(true);
              return;
            }
            const registerResponse = await fetch(`${API_BASE}/state`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                uid,
                name: storedName,
                gameUid: activeGameUid,
                state: {
                  grid: createEmptyGrid(maxGuesses, wordLength),
                  currentRow: 0,
                  currentCol: 0,
                  keyboardStatuses: {},
                  gameOver: false,
                  isWinner: false,
                  startTime,
                  maxGuesses,
                  wordLength
                }
              })
            });
            if (registerResponse.ok) {
              setPlayerName(storedName);
              setPendingName(storedName);
              setNameError("");
              setShowNamePrompt(false);
            } else if (registerResponse.status === 409) {
              setNameError(
                "That name is already in use, choose a different name."
              );
              setPlayerName("");
              setPendingName(storedName);
              setShowNamePrompt(true);
            } else {
              updateMessage("Unable to save name.");
              setPendingName(storedName);
              setNameError("");
              setShowNamePrompt(true);
            }
          } else {
            setShowNamePrompt(true);
          }
        }
      } catch (error) {
        updateMessage("Unable to load saved game.");
      } finally {
        hasLoadedStateRef.current = true;
      }
    };
    fetchState();
  }, [configLoaded, gameUid, loadScores, resolveActiveGameUid, uid]);

  useEffect(() => {
    if (playerScoreRef.current && scoreContainerRef.current) {
      playerScoreRef.current.scrollIntoView({ block: "center" });
    }
  }, [scores]);

  useEffect(() => {
    if (!isWinner || showScoresOverlay) {
      return;
    }
    const handleClick = () => {
      setShowScoresOverlay(true);
    };
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [isWinner, showScoresOverlay]);

  const applyKeyboardStatus = useCallback((letter, status) => {
    setKeyboardStatuses((prev) => {
      const current = prev[letter];
      if (!current || statusPriority[status] > statusPriority[current]) {
        return { ...prev, [letter]: status };
      }
      return prev;
    });
  }, []);

  const resetForNewGame = useCallback(
    ({ nextGameUid, nextWordLength, nextMaxGuesses }) => {
      clearStoredGameState();
      setGameUid(nextGameUid);
      if (nextGameUid) {
        setStored(gameUidStorageKey(), nextGameUid);
      }
      if (nextWordLength) {
        setWordLength(nextWordLength);
      }
      if (nextMaxGuesses) {
        setMaxGuesses(nextMaxGuesses);
      }
      const gridRows = nextMaxGuesses || maxGuesses;
      const gridCols = nextWordLength || wordLength;
      setGrid(createEmptyGrid(gridRows, gridCols));
      setCurrentRow(0);
      setCurrentCol(0);
      setKeyboardStatuses({});
      setMessage("");
      setInvalidGuessActive(false);
      setGameOver(false);
      setIsWinner(false);
      setShowHelp(false);
      const storedName = getStored("wordly_name") || "";
      setShowNamePrompt(!storedName);
      setPlayerName("");
      setPendingName(storedName);
      setNameError("");
      setScores([]);
      setPlayerScore(null);
      setSolutionWord("");
      setSolutionDefinition("");
      setStartTime(Date.now());
      setShowScoresOverlay(false);
      hasLoadedStateRef.current = false;
    },
    [maxGuesses, uid, wordLength]
  );

  const submitGuess = useCallback(
    async (guess) => {
      try {
        const configResponse = await fetch(`${API_BASE}/config`);
        if (!configResponse.ok) {
          throw new Error("config");
        }
        const configData = await configResponse.json();
        const storedGameUid = getStored(gameUidStorageKey());
        if (
          configData.gameUid
          && (configData.gameUid !== gameUid || configData.gameUid !== storedGameUid)
        ) {
          resetForNewGame({
            nextGameUid: configData.gameUid,
            nextWordLength: configData.wordLength,
            nextMaxGuesses: configData.maxGuesses
          });
          updateMessage("Reset for new game");
          return;
        }
        const response = await fetch(`${API_BASE}/guess`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            guess,
            gameUid,
            uid,
            name: playerName
          })
        });
        if (!response.ok) {
          const errorData = await response.json();
          if (response.status === 409 && errorData.nextGameUid) {
            resetForNewGame({
              nextGameUid: errorData.nextGameUid,
              nextWordLength: errorData.wordLength,
              nextMaxGuesses: errorData.maxGuesses
            });
            updateMessage(errorData.error || "Reset for new game");
            return;
          }
          const errorText = errorData.error || "Guess rejected.";
          const isInvalidWord = errorText === "That is not a word.";
          updateMessage(errorText, { autoClear: !isInvalidWord });
          if (isInvalidWord) {
            setInvalidGuessActive(true);
          }
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
          setShowScoresOverlay(true);
          setShowHelp(false);
          setStored("wordly_help_seen", "1");
          updateMessage("Genius!");
          setSolutionWord(data.word || "");
          setSolutionDefinition(data.definition || "");
          await loadScores();
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
    [
      applyKeyboardStatus,
      currentRow,
      gameUid,
      loadScores,
      maxGuesses,
      playerName,
      resetForNewGame,
      uid
    ]
  );

  useEffect(() => {
    if (!hasLoadedStateRef.current || !playerName || !gameUid) {
      return;
    }
    const persistState = async () => {
      try {
        const response = await fetch(`${API_BASE}/state`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            uid,
            name: playerName,
            gameUid,
            state: {
              grid,
              currentRow,
              currentCol,
              keyboardStatuses,
              gameOver,
              isWinner,
              startTime,
              maxGuesses,
              wordLength
            }
          })
        });
        if (!response.ok) {
          const errorData = await response.json();
          if (response.status === 409 && errorData.nextGameUid) {
            resetForNewGame({
              nextGameUid: errorData.nextGameUid,
              nextWordLength: errorData.wordLength,
              nextMaxGuesses: errorData.maxGuesses
            });
            updateMessage(errorData.error || "Reset for new game");
          }
        }
      } catch (error) {
        updateMessage("Unable to save game.");
      }
    };
    persistState();
  }, [
    currentCol,
    currentRow,
    gameOver,
    grid,
    gameUid,
    isWinner,
    keyboardStatuses,
    maxGuesses,
    playerName,
    startTime,
    uid,
    wordLength
  ]);

  const handleKeyPress = useCallback(
    (value) => {
      if (gameOver || showNamePrompt) {
        return;
      }
      const shouldResetInvalid = invalidGuessActive;
      const key = value.toUpperCase();
      let nextCol = currentCol;
      if (shouldResetInvalid) {
        updateMessage("");
        setInvalidGuessActive(false);
        setGrid((prev) => {
          const next = prev.map((row) => row.map((cell) => ({ ...cell })));
          next[currentRow] = next[currentRow].map(() => ({ letter: "", status: "" }));
          return next;
        });
        setCurrentCol(0);
        nextCol = 0;
      }
      if (key === "ENTER") {
        if (nextCol < wordLength) {
          updateMessage("Not enough letters");
          return;
        }
        const guess = grid[currentRow].map((cell) => cell.letter).join("");
        submitGuess(guess);
        return;
      }
      if (key === "⌫" || key === "BACKSPACE") {
        if (nextCol === 0) {
          return;
        }
        const targetCol = nextCol - 1;
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
        if (nextCol >= wordLength) {
          return;
        }
        setGrid((prev) => {
          const next = prev.map((row) => row.map((cell) => ({ ...cell })));
          next[currentRow][nextCol].letter = key;
          next[currentRow][nextCol].status = "";
          return next;
        });
        setCurrentCol(nextCol + 1);
      }
    },
    [
      currentCol,
      currentRow,
      gameOver,
      grid,
      invalidGuessActive,
      showNamePrompt,
      submitGuess,
      wordLength
    ]
  );

  useEffect(() => {
    const handleKeyDown = (event) => handleKeyPress(event.key);
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyPress]);

  const handleNameSubmit = async (event) => {
    event.preventDefault();
    if (!pendingName.trim()) {
      return;
    }
    const cleaned = pendingName.trim();
    setStored("wordly_name", cleaned);
    const activeGameUid = await resolveActiveGameUid(gameUid);
    if (!activeGameUid) {
      updateMessage("Unable to connect to the game server.");
      setNameError("");
      setShowNamePrompt(true);
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/state`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          uid,
          name: cleaned,
          gameUid: activeGameUid,
          state: {
            grid,
            currentRow,
            currentCol,
            keyboardStatuses,
            gameOver,
            isWinner,
            startTime,
            maxGuesses,
            wordLength
          }
        })
      });
      if (!response.ok) {
        const errorData = await response.json();
        if (response.status === 409 && errorData.nextGameUid) {
          resetForNewGame({
            nextGameUid: errorData.nextGameUid,
            nextWordLength: errorData.wordLength,
            nextMaxGuesses: errorData.maxGuesses
          });
          updateMessage(errorData.error || "Reset for new game");
          setNameError("");
          return;
        }
        if (response.status === 409) {
          setNameError(
            "That name is already in use, choose a different name."
          );
        } else {
          updateMessage(errorData.error || "Unable to save name.");
          setNameError("");
        }
        setShowNamePrompt(true);
        return;
      }
      setPlayerName(cleaned);
      setPendingName(cleaned);
      setNameError("");
      setStored("wordly_name", cleaned);
      setShowNamePrompt(false);
    } catch (error) {
      updateMessage("Unable to save name.");
      setNameError("");
    }
  };

  const helpModalRef = useRef(null);

  const closeHelp = () => {
    setStored("wordly_help_seen", "1");
    setShowHelp(false);
  };

  useEffect(() => {
    if (showHelp) {
      helpModalRef.current?.focus();
    }
  }, [showHelp]);

  const scoresToRender =
    scores.length === 0 && playerScore ? [playerScore] : scores;

  const scoreRows = scoresToRender.map((entry) => {
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
      </div>
    );
  });

  return (
    <div className="app">
      <header className="header">
        <h1>
          {playerName
            ? `FSQ ${playerName}'s attempt #${Math.min(
                currentRow + 1,
                maxGuesses
              )}`
            : "FSQ Wordly"}
        </h1>
        <button type="button" className="help-button" onClick={() => setShowHelp(true)}>
          ?
        </button>
      </header>
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
      <div className="message-area">{message && <div className="toast">{message}</div>}</div>

      {showHelp && (
        <div
          className="modal"
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              closeHelp();
            }
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              closeHelp();
            }
          }}
          ref={helpModalRef}
          tabIndex={-1}
        >
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
                value={pendingName}
                onChange={(event) => {
                  setPendingName(event.target.value);
                  if (nameError) {
                    setNameError("");
                  }
                }}
                placeholder="Your name"
                maxLength={20}
              />
              {nameError && <p className="name-error">{nameError}</p>}
              <button type="submit">Start</button>
            </form>
          </div>
        </div>
      )}

      {isWinner && showScoresOverlay && (
        <div className="modal">
          <div className="modal-content scores">
            <h2>Hi Scores</h2>
            <div className="score-container" ref={scoreContainerRef}>
              {scoreRows.length ? scoreRows : <p>No scores yet.</p>}
            </div>
            <p className="score-note">
              Ranked by fewest tries, then fastest time.
            </p>
            {solutionWord && (
              <p className="score-solution">
                {`${solutionWord}: ${solutionDefinition}`}
              </p>
            )}
            <button
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                setShowScoresOverlay(false);
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default function App() {
  const isAdminRoute = window.location.pathname === "/admin";
  if (isAdminRoute) {
    return <AdminPanel />;
  }
  return <GameApp />;
}
