import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  DEFAULT_KEYBOARD,
  STATUS_PRIORITY,
  STORAGE_KEYS
} from "../config";
import {
  fetchConfig,
  fetchScores,
  fetchState,
  persistState,
  submitGuessRequest
} from "../services/api";
import {
  clearStoredGameState,
  generateUid,
  getStored,
  setStored
} from "../services/storage";
import { createEmptyGrid } from "../utils/gameState";
import MessageToast from "./MessageToast";
import ScoreBoard from "./ScoreBoard";

export default function GameApp() {
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
  const helpModalRef = useRef(null);

  const uid = useMemo(() => {
    let stored = getStored(STORAGE_KEYS.uid);
    if (!stored) {
      stored = generateUid();
      setStored(STORAGE_KEYS.uid, stored);
    }
    return stored;
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

  const resolveActiveGameUid = useCallback(async (currentGameUid) => {
    const storedGameUid = getStored(STORAGE_KEYS.gameUid);
    const fallbackGameUid = currentGameUid || storedGameUid;

    try {
      const configData = await fetchConfig();
      if (configData.gameUid && configData.gameUid !== fallbackGameUid) {
        setGameUid(configData.gameUid);
        setStored(STORAGE_KEYS.gameUid, configData.gameUid);
      }
      return configData.gameUid || fallbackGameUid;
    } catch {
      return fallbackGameUid || null;
    }
  }, []);

  const loadScores = useCallback(async () => {
    try {
      const scoreData = await fetchScores();
      setScores(scoreData);
      const matchingScore = scoreData.find((entry) => entry.uid === uid);
      setPlayerScore(matchingScore || null);
    } catch {
      updateMessage("Unable to load scores.");
    }
  }, [uid, updateMessage]);

  const resetForNewGame = useCallback(
    ({ nextGameUid, nextWordLength, nextMaxGuesses }) => {
      clearStoredGameState();
      setGameUid(nextGameUid);
      if (nextGameUid) {
        setStored(STORAGE_KEYS.gameUid, nextGameUid);
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
      const storedName = getStored(STORAGE_KEYS.playerName) || "";
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
    [maxGuesses, wordLength]
  );

  const applyKeyboardStatus = useCallback((letter, status) => {
    setKeyboardStatuses((previousStatuses) => {
      const current = previousStatuses[letter];
      if (!current || STATUS_PRIORITY[status] > STATUS_PRIORITY[current]) {
        return { ...previousStatuses, [letter]: status };
      }
      return previousStatuses;
    });
  }, []);

  const submitGuess = useCallback(
    async (guess) => {
      try {
        const configData = await fetchConfig();
        const storedGameUid = getStored(STORAGE_KEYS.gameUid);
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

        const data = await submitGuessRequest({ guess, gameUid, uid, name: playerName });

        setGrid((previousGrid) => {
          const next = previousGrid.map((row) => row.map((cell) => ({ ...cell })));
          data.statuses.forEach((status, index) => {
            next[currentRow][index] = { letter: guess[index], status };
          });
          return next;
        });

        data.statuses.forEach((status, index) => applyKeyboardStatus(guess[index], status));

        if (data.isCorrect) {
          setGameOver(true);
          setIsWinner(true);
          setShowScoresOverlay(true);
          setShowHelp(false);
          setStored(STORAGE_KEYS.helpSeen, "1");
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
        if (error.status === 409 && error.data?.nextGameUid) {
          resetForNewGame({
            nextGameUid: error.data.nextGameUid,
            nextWordLength: error.data.wordLength,
            nextMaxGuesses: error.data.maxGuesses
          });
          updateMessage(error.message || "Reset for new game");
          return;
        }

        const isInvalidWord = error.message === "That is not a word.";
        updateMessage(error.message || "Guess rejected.", { autoClear: !isInvalidWord });
        if (isInvalidWord) {
          setInvalidGuessActive(true);
        }
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
      uid,
      updateMessage
    ]
  );

  useEffect(() => {
    fetchConfig()
      .then((data) => {
        const nextGameUid = data.gameUid || null;
        setWordLength(data.wordLength);
        setMaxGuesses(data.maxGuesses);
        setGrid(createEmptyGrid(data.maxGuesses, data.wordLength));
        setGameUid(nextGameUid);
        if (nextGameUid) {
          setStored(STORAGE_KEYS.gameUid, nextGameUid);
        }
        setConfigLoaded(true);
      })
      .catch(() => updateMessage("Unable to load game config."));
  }, [uid, updateMessage]);

  useEffect(() => {
    if (!getStored(STORAGE_KEYS.helpSeen)) {
      setShowHelp(true);
    }
  }, []);

  useEffect(() => {
    if (!configLoaded || hasLoadedStateRef.current) {
      return;
    }

    const loadGameState = async () => {
      try {
        const data = await fetchState(uid);
        if (data.state) {
          const state = data.state;
          if (gameUid) {
            setStored(STORAGE_KEYS.gameUid, gameUid);
          }
          setWordLength(state.wordLength || wordLength);
          setMaxGuesses(state.maxGuesses || maxGuesses);
          setGrid(state.grid || createEmptyGrid(maxGuesses, wordLength));
          setCurrentRow(state.currentRow ?? 0);
          setCurrentCol(state.currentCol ?? 0);
          setKeyboardStatuses(state.keyboardStatuses || {});
          setGameOver(state.gameOver || false);
          setIsWinner(state.isWinner || false);
          setShowScoresOverlay(state.isWinner || false);
          if (state.isWinner) {
            setShowHelp(false);
            setStored(STORAGE_KEYS.helpSeen, "1");
          }
          setStartTime(state.startTime || Date.now());
          setPlayerName(state.name || "");
          setPendingName(state.name || "");
          setNameError("");
          if (state.name) {
            setStored(STORAGE_KEYS.playerName, state.name);
            setShowNamePrompt(false);
          } else {
            setShowNamePrompt(true);
          }
          if (state.isWinner) {
            await loadScores();
          }
        } else {
          const storedName = getStored(STORAGE_KEYS.playerName);
          if (!storedName) {
            setShowNamePrompt(true);
            return;
          }

          const activeGameUid = await resolveActiveGameUid(gameUid);
          if (!activeGameUid) {
            updateMessage("Unable to connect to the game server.");
            setPendingName(storedName);
            setShowNamePrompt(true);
            return;
          }

          try {
            await persistState({
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
            });
            setPlayerName(storedName);
            setPendingName(storedName);
            setNameError("");
            setShowNamePrompt(false);
          } catch (error) {
            if (error.status === 409) {
              setNameError("That name is already in use, choose a different name.");
              setPlayerName("");
            } else {
              updateMessage("Unable to save name.");
            }
            setPendingName(storedName);
            setShowNamePrompt(true);
          }
        }
      } catch {
        updateMessage("Unable to load saved game.");
      } finally {
        hasLoadedStateRef.current = true;
      }
    };

    loadGameState();
  }, [
    configLoaded,
    gameUid,
    loadScores,
    maxGuesses,
    resolveActiveGameUid,
    startTime,
    uid,
    updateMessage,
    wordLength
  ]);

  useEffect(() => {
    if (playerScoreRef.current && scoreContainerRef.current) {
      playerScoreRef.current.scrollIntoView({ block: "center" });
    }
  }, [scores]);

  useEffect(() => {
    if (!isWinner || showScoresOverlay) {
      return;
    }
    const handleClick = () => setShowScoresOverlay(true);
    window.addEventListener("click", handleClick);
    return () => window.removeEventListener("click", handleClick);
  }, [isWinner, showScoresOverlay]);

  useEffect(() => {
    if (!hasLoadedStateRef.current || !playerName || !gameUid) {
      return;
    }

    persistState({
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
    }).catch((error) => {
      if (error.status === 409 && error.data?.nextGameUid) {
        resetForNewGame({
          nextGameUid: error.data.nextGameUid,
          nextWordLength: error.data.wordLength,
          nextMaxGuesses: error.data.maxGuesses
        });
        updateMessage(error.message || "Reset for new game");
        return;
      }
      updateMessage("Unable to save game.");
    });
  }, [
    currentCol,
    currentRow,
    gameOver,
    gameUid,
    grid,
    isWinner,
    keyboardStatuses,
    maxGuesses,
    playerName,
    resetForNewGame,
    startTime,
    uid,
    updateMessage,
    wordLength
  ]);

  const handleKeyPress = useCallback(
    (value) => {
      if (gameOver || showNamePrompt) {
        return;
      }

      const key = value.toUpperCase();
      let nextCol = currentCol;

      if (invalidGuessActive) {
        updateMessage("");
        setInvalidGuessActive(false);
        setGrid((previousGrid) => {
          const next = previousGrid.map((row) => row.map((cell) => ({ ...cell })));
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
        setGrid((previousGrid) => {
          const next = previousGrid.map((row) => row.map((cell) => ({ ...cell })));
          next[currentRow][targetCol].letter = "";
          next[currentRow][targetCol].status = "";
          return next;
        });
        setCurrentCol(targetCol);
        return;
      }

      if (/^[A-Z]$/.test(key) && nextCol < wordLength) {
        setGrid((previousGrid) => {
          const next = previousGrid.map((row) => row.map((cell) => ({ ...cell })));
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
      updateMessage,
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
    setStored(STORAGE_KEYS.playerName, cleaned);
    const activeGameUid = await resolveActiveGameUid(gameUid);

    if (!activeGameUid) {
      updateMessage("Unable to connect to the game server.");
      setNameError("");
      setShowNamePrompt(true);
      return;
    }

    try {
      await persistState({
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
      });
      setPlayerName(cleaned);
      setPendingName(cleaned);
      setNameError("");
      setShowNamePrompt(false);
    } catch (error) {
      if (error.status === 409 && error.data?.nextGameUid) {
        resetForNewGame({
          nextGameUid: error.data.nextGameUid,
          nextWordLength: error.data.wordLength,
          nextMaxGuesses: error.data.maxGuesses
        });
        updateMessage(error.message || "Reset for new game");
        setNameError("");
        return;
      }
      if (error.status === 409) {
        setNameError("That name is already in use, choose a different name.");
      } else {
        updateMessage(error.message || "Unable to save name.");
        setNameError("");
      }
      setShowNamePrompt(true);
    }
  };

  const closeHelp = () => {
    setStored(STORAGE_KEYS.helpSeen, "1");
    setShowHelp(false);
  };

  useEffect(() => {
    if (showHelp) {
      helpModalRef.current?.focus();
    }
  }, [showHelp]);

  return (
    <div className="app">
      <header className="header">
        <h1>
          {playerName
            ? `FSQ ${playerName}'s attempt #${Math.min(currentRow + 1, maxGuesses)}`
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
              <div key={`cell-${rowIndex}-${colIndex}`} className={`cell ${cell.status}`}>
                {cell.letter}
              </div>
            ))}
          </div>
        ))}
      </section>

      <section className="keyboard">
        {DEFAULT_KEYBOARD.map((row, rowIndex) => (
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

      <MessageToast message={message} />

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
        <ScoreBoard
          scores={scores}
          playerScore={playerScore}
          scoreContainerRef={scoreContainerRef}
          playerScoreRef={playerScoreRef}
          solutionWord={solutionWord}
          solutionDefinition={solutionDefinition}
          onClose={() => setShowScoresOverlay(false)}
        />
      )}
    </div>
  );
}
