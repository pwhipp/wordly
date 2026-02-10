import { useEffect, useState } from "react";
import { fetchScores, resetGame, verifyAdminCode } from "../services/api";

export default function AdminPanel() {
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
        const data = await verifyAdminCode(adminCode);
        setCodeValid(Boolean(data.valid));
        setStatusMessage(data.valid ? "" : "Admin code is incorrect.");
      } catch {
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
      await resetGame(adminCode);
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
      const scores = await fetchScores();
      if (scores.length === 0) {
        setShowConfirm(true);
        return;
      }
      await performReset();
    } catch {
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
            <p>Nobody has completed this puzzle yet. Are you sure you want to reset it?</p>
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
}
